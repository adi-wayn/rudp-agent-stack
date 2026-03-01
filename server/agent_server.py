"""
Agent Server Module.
Main entry point for the Agent-based Application Server.
Orchestrates the request processing pipeline.
"""
import logging
from typing import Tuple

from common.app_envelope import decode_header, encode_message
from common.errors import ErrorCode

from server.agent.validations import PolicyGuard
from server.agent.idempotency import IdempotencyCache
from server.agent.dispatcher import Dispatcher
from server.agent.upload_session import UploadSessionManager, UploadMode
from server.transport.tcp_server import TCPServerTransport
from common.app_envelope import HEADER_SIZE

logger = logging.getLogger(__name__)

class AgentServer:
    """
    Agent Server Application Logic.
    Decoupled from Transport Layer (handled by Transport adapters).
    """
    def __init__(self, sandbox_root: str, transport=None):
        self.sandbox_root = sandbox_root
        # Day 3 Refactor: Agent owns transport (Client pattern)
        self.transport = transport or TCPServerTransport()
        
        global logger
        is_async = getattr(self.transport, 'is_async', not hasattr(self.transport, 'accept')) is True
        logger = logging.getLogger("Agent-RUDP" if is_async else "Agent-TCP")
        
        # 1. Initialize Components
        self.policy_guard = PolicyGuard(sandbox_root)
        self.idempotency_cache = IdempotencyCache()
        
        # Day 3: Upload Session Manager (Strict Mode by default)
        self.session_manager = UploadSessionManager(upload_mode=UploadMode.STRICT)
        
        self.dispatcher = Dispatcher(self.policy_guard, self.session_manager, self.idempotency_cache)
        
        logger.info(f"AgentServer initialized with sandbox: {sandbox_root}")

    def process_request(self, client_id: str, data: bytes) -> bytes:
        """
        Core Pipeline:
        1. Decode Header
        2. Check Idempotency
        3. Dispatch (which handles Response Building)
        4. Store Result
        """
        try:
            # 1. Transport -> Decoder
            # Handle empty data gracefully
            if not data:
                return b''
                
            header = decode_header(data[:12])
            payload = data[12:]
            
            # Sub-step: Validate Payload Length against Header
            if len(payload) != header.payload_len:
                logger.warning(f"Payload length mismatch: Header={header.payload_len}, Actual={len(payload)}")
                # Critical transport/framing error. Drop or return nothing as we can't trust header.
                return b''

            # 2. Idempotency Check
            cached_response = self.idempotency_cache.get_response(
                client_id, header.request_id, header.opcode
            )
            if cached_response:
                logger.warning(f"Idempotency Cache HIT: Duplicate packet caught for Client={client_id}, ReqID={header.request_id}, Opcode={header.opcode}. Returning cached response.")
                return cached_response

            # 3. Policy & Dispatch
            # Dispatcher now returns FULL ENCODED RESPONSE BYTES (Header + JSON Payload)
            response_bytes = self.dispatcher.dispatch(header, payload)
            
            # 4. Store Result
            self.idempotency_cache.store_response(
                client_id, header.request_id, header.opcode, response_bytes
            )
            
            logger.info(f"Agent Request Completed: Client={client_id}, ReqID={header.request_id}, Opcode={header.opcode}. Returning {len(response_bytes)} bytes.")
            return response_bytes

        except ValueError as e:
            logger.error(f"Header Decode Validation Error: {e}")
            # If header decode fails, we can't get RequestID to send error back.
            return b''

        except Exception as e:
            logger.error(f"Unexpected Server Error: {e}", exc_info=True)
            return b''

    def run(self):
        """
        Main Server Loop (Driver).
        """
        if hasattr(self.transport, 'set_message_handler'):
            self.transport.set_message_handler(self._on_udp_message)

        self.transport.start()
        # Since RUDPServerTransport might not have is_async defined yet, let's gracefully fallback
        # by checking if it has 'accept' method. If it doesn't, it's the async UDP transport.
        is_async = getattr(self.transport, 'is_async', not hasattr(self.transport, 'accept')) is True
        
        try:
            if is_async:
                # RUDP Mode: Keep the main thread alive. 
                # (RUDPServerTransport.start() blocks its own internal receive_loop,
                # but if it was wrapped in a daemon thread later, this guarantees the server stays alive)
                import time
                while True:
                    time.sleep(1)
            else:
                # TCP Mode: Synchronous Accept Loop
                while True:
                    conn, addr = self.transport.accept()
                    self._handle_connection(conn, addr)
        except KeyboardInterrupt:
            logger.info("AgentServer stopping...")
        finally:
            self.transport.close()

    def _handle_connection(self, conn, addr):
        """
        Handle individual connection using transport primitives.
        """
        client_id = f"{addr[0]}:{addr[1]}"
        logger.info(f"Accepted connection from {client_id}")
        
        try:
            while True:
                # 1. Read Header
                try:
                    header_bytes = self.transport.receive_exact(conn, HEADER_SIZE)
                except ConnectionError:
                    logger.info(f"Client {client_id} disconnected.")
                    break
                
                # 2. Decode for length
                try:
                    header = decode_header(header_bytes)
                except ValueError as e:
                    logger.error(f"Header error from {client_id}: {e}")
                    break
                
                # 3. Read Payload
                try:
                    payload = self.transport.receive_exact(conn, header.payload_len)
                except ConnectionError:
                    break
                
                # 4. Process
                full_message = header_bytes + payload
                response = self.process_request(client_id, full_message)
                
                # 5. Send (Polymorphic)
                if response:
                    self.transport.send(response, header.request_id, addr)
                    
        except Exception as e:
            logger.error(f"Error handling {client_id}: {e}")
        finally:
            conn.close()
            # Clean up the lookup dict
            if hasattr(self.transport, 'active_conns'):
                self.transport.active_conns.pop(addr, None)

    def _on_udp_message(self, data: bytes, client_addr: Tuple[str, int]) -> None:
        """
        Callback triggered by RUDPServerTransport when a complete, valid AppEnvelope is reassembled.
        Bypasses conventional streaming accept() mechanics in favor of atomic message processing.
        """
        if len(data) < HEADER_SIZE:
            return
            
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        try:
            header = decode_header(data[:HEADER_SIZE])
            response = self.process_request(client_id, data)
            
            if response:
                # Polymorphic push back down to transport using original client_addr tuple
                self.transport.send(response, header.request_id, client_addr)
                
        except Exception as e:
            logger.error(f"Error processing UDP message from {client_id}: {e}")
