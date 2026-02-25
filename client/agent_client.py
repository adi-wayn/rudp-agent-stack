"""
Agent Client Module.
Interacts with the Agent Server using a Dispatcher-based architecture.
"""
import json
import time
import logging
import socket
import threading
from typing import Any, Dict, Optional, Tuple, Union

from client.transport.tcp_client import TCPClient
from common.app_envelope import encode_message, decode_header, HEADER_SIZE
from common.constants import (
    PROTOCOL_VERSION, MAX_RETRIES, INITIAL_RTO, MAX_RTO, MAX_PAYLOAD_LEN,
    OP_GET, OP_APPEND, OP_LIST, OP_PUT_META, OP_PUT_CHUNK, OP_UPLOAD
)
from common.mixed_mode_io import MixedModeEncoder, MixedModeDecoder

# Dispatcher & Handlers
from client.agent.dispatcher import (
    ClientDispatcher, ClientRequestSpec, OperationResult,
    ENCODING_JSON, ENCODING_MIXED
)
from client.agent.handlers.get import GetHandler
from client.agent.handlers.append import AppendHandler
from client.agent.handlers.list import ListHandler
from client.agent.handlers.put_meta import PutMetaHandler
from client.agent.handlers.put_chunk import PutChunkHandler
from client.agent.handlers.upload import UploadHandler
from client.agent.handlers.task import TaskHandler
from common.constants import (
    OP_TASK_SEARCH_REPORT, OP_TASK_FILTER_LINES, OP_TASK_HASH_AND_STORE
)


logger = logging.getLogger("AgentClient")

class RequestIdManager:
    """
    Manages unique monotonic Request IDs.
    """
    def __init__(self):
        self._current_id = 0

    def next_id(self) -> int:
        self._current_id += 1
        return self._current_id

class AgentClient:
    """
    Client for the Agent Protocol.
    Authority for:
    1. Transport (TCP Socket, Framing, Retries)
    2. Encoding Policy (Common Utils)
    3. Decoding Policy (Status-Aware)
    """
    def __init__(self, transport=None):
        self.transport = transport or TCPClient()
        self.request_id_manager = RequestIdManager()
        
        # Day 8 - Async Responses
        self._pending_requests: Dict[int, Dict[str, Any]] = {}
        if getattr(self.transport, 'is_async', False) is True:
            if hasattr(self.transport, 'set_message_handler'):
                self.transport.set_message_handler(self._on_message_received)
        
        # Initialize Dispatcher and Register Handlers
        self.dispatcher = ClientDispatcher()
        self.dispatcher.register(OP_GET, GetHandler())
        self.dispatcher.register(OP_APPEND, AppendHandler())
        self.dispatcher.register(OP_LIST, ListHandler())
        self.dispatcher.register(OP_PUT_META, PutMetaHandler())
        self.dispatcher.register(OP_PUT_CHUNK, PutChunkHandler())
        self.dispatcher.register(OP_UPLOAD, UploadHandler())
        
        # Day 5: Task Handlers (Orchestrators)
        self.dispatcher.register(OP_TASK_SEARCH_REPORT, TaskHandler(OP_TASK_SEARCH_REPORT))
        self.dispatcher.register(OP_TASK_FILTER_LINES, TaskHandler(OP_TASK_FILTER_LINES))
        self.dispatcher.register(OP_TASK_HASH_AND_STORE, TaskHandler(OP_TASK_HASH_AND_STORE))

    def _on_message_received(self, data: bytes) -> None:
        """
        Async delivery callback from RUDP Transport.
        Extracts the request_id from the envelope and triggers the awaiting Event.
        """
        if len(data) < HEADER_SIZE:
            return
            
        try:
            header = decode_header(data[:HEADER_SIZE])
            req_id = header.request_id
            
            if req_id in self._pending_requests:
                self._pending_requests[req_id]["response"] = data
                self._pending_requests[req_id]["event"].set()
            else:
                logger.warning(f"Discarded late or unknown packet for ReqID: {req_id}")
        except Exception as e:
            logger.error(f"Failed to process async packet: {e}")

    def execute(self, opcode: int, request_id_override: Optional[int] = None, **kwargs) -> OperationResult:
        """
        Execute an operation by opcode.
        Delegates request building to handler, then orchestrates transport.
        Supports:
        1. Request/Response Handlers (build -> send -> parse)
        2. Orchestrator Handlers (run)
        """
        # Backward compatibility for kwargs injection
        if request_id_override is None:
            request_id_override = kwargs.pop("request_id_override", None)
        else:
            kwargs.pop("request_id_override", None)
            
        handler = self.dispatcher.get_handler(opcode)
        
        # Determine active override locally
        inherited_override = getattr(self, "_active_request_override", None)
        active_override = request_id_override if request_id_override is not None else inherited_override
        
        # Save previous state and apply current override
        previous_override = getattr(self, "_active_request_override", None)
        if active_override is not None:
             self._active_request_override = active_override

        try:
            # Support High-Level Orchestrators
            if getattr(handler, "is_orchestrator", False):
                return handler.run(self, **kwargs)

            # 1. Build Request Spec
            req_spec = handler.build_request(**kwargs)
            
            # 2. Send & Receive (Retry Loop)
            # send_request_spec will consume the _active_request_override
            status, resp_meta, resp_binary = self.send_request_spec(req_spec)
            
            # 3. Parse Response via Handler
            return handler.parse_response(status, resp_meta, resp_binary)
        finally:
            self._active_request_override = previous_override

    def send_request_spec(self, spec: ClientRequestSpec) -> Tuple[int, Dict[str, Any], Optional[bytes]]:
        """
        Public method to encode, send, receive, and decode a request spec.
        Used by Orchestrators that need to send raw requests.
        Returns: (status_code, meta_dict, binary_bytes)
        """
        # A. Encode Payload based on Spec Mode
        if spec.encoding_mode == ENCODING_MIXED:
             payload_bytes = MixedModeEncoder.encode(spec.meta, spec.binary)
        else:
             # Default JSON
             payload_bytes = json.dumps(spec.meta).encode("utf-8")
        
        # Check instance state for override, and consume it immediately 
        # so it only applies explicitly to the NEXT logical envelope creation.
        override = getattr(self, "_active_request_override", None)
        self._active_request_override = None 
        
        generated_id = self.request_id_manager.next_id()
        # The request_id field logic is done natively in app_envelope now
        final_req_id = override if override is not None else generated_id
        
        retries = 0

        while retries <= MAX_RETRIES:
            try:

                # 2. Build Envelope
                full_message = encode_message(spec.opcode, 0, generated_id, payload_bytes, request_id_override=override)
                
                is_async = getattr(self.transport, 'is_async', False) is True
                
                if is_async:
                    # RUDP Flow: Event driven
                    event = threading.Event()
                    self._pending_requests[final_req_id] = {"event": event, "response": None}
                    
                    self.transport.send(full_message, final_req_id)
                    
                    # Generous wait. RUDP naturally handles its own micro-retries and timeouts.
                    timeout_val = 15.0
                    
                    if not event.wait(timeout=timeout_val):
                        self._pending_requests.pop(final_req_id, None)
                        raise TimeoutError(f"RUDP response timed out after {timeout_val}s")
                        
                    response_data = self._pending_requests.pop(final_req_id)["response"]
                    header = decode_header(response_data[:HEADER_SIZE])
                    
                    if header.payload_len > MAX_PAYLOAD_LEN:
                        raise ValueError(f"Payload too large: {header.payload_len}")
                        
                    payload_data = response_data[HEADER_SIZE:HEADER_SIZE+header.payload_len]
                
                else:
                    # TCP Flow: Synchronous
                    # 3. Send
                    self.transport.send_bytes(full_message)
                    
                    # 4. Receive Header
                    header_data = self.transport.receive_exact(HEADER_SIZE)
                    header = decode_header(header_data)
                    
                    # Validation
                    if header.payload_len > MAX_PAYLOAD_LEN:
                        raise ValueError(f"Payload too large: {header.payload_len}")
                        
                    if header.request_id != final_req_id:
                         # Strict check
                         self.transport.close()
                         raise ConnectionError("Request ID Mismatch")
                         
                    # 5. Receive Payload
                    payload_data = self.transport.receive_exact(header.payload_len)
                
                # 6. Decode Strategy (Status-Aware)
                
                resp_meta = {}
                resp_binary = None
                status = 200 # Default assumption if not found
                
                # Attempt Mixed Mode Decode
                is_mixed = False
                try:
                    # Only attempt if payload is large enough for prefix
                    if len(payload_data) >= 4: 
                        resp_meta, resp_binary = MixedModeDecoder.decode(payload_data)
                        is_mixed = True
                        status = resp_meta.get("status", 200)
                except ValueError:
                    # Not mixed mode
                    pass
                    
                if not is_mixed:
                    # Try Pure JSON
                    try:
                        resp_meta = json.loads(payload_data.decode("utf-8"))
                        status = resp_meta.get("status", 200)
                        resp_binary = None
                    except json.JSONDecodeError:
                         # Fallback for unparseable payload (legacy or raw error?)
                         # Re-raise unless empty
                         if not payload_data:
                             pass
                         else:
                             raise ValueError(f"Invalid response format: {payload_data[:100]}")

                return status, resp_meta, resp_binary

            except (ConnectionError, TimeoutError, socket.timeout, ValueError) as e:
                logger.warning(f"Retryable Error ({retries}/{MAX_RETRIES}): {e}")
                
                # Only close synchronous transports on error to avoid destroying background threads
                if not getattr(self.transport, 'is_async', False):
                    self.transport.close()
                    
                retries += 1
                if retries > MAX_RETRIES:
                    raise TimeoutError(f"Max retries exceeded for ReqID={final_req_id}") from e
                
                time.sleep(min(INITIAL_RTO * (2 ** (retries - 1)), MAX_RTO))
                
        raise TimeoutError("Unreachable")
        
    def close(self):
        self.transport.close()
