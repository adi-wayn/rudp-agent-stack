"""
Agent Client Module.
Interacts with the Agent Server to submit tasks using the defined application envelope.
"""
import json
import time
import logging
import socket
from typing import Any, Dict, Optional, Tuple
from common.constants import OP_APPEND

from client.transport.tcp_client import TCPClient
from common.app_envelope import encode_message, decode_header, HEADER_SIZE
from common.constants import (
    PROTOCOL_VERSION,
    MAX_RETRIES,
    INITIAL_RTO,
    MAX_RTO,
    MAX_PAYLOAD_LEN
)

logger = logging.getLogger("AgentClient")

class RequestIdManager:
    """
    Manages unique monotonic Request IDs.
    """
    def __init__(self):
        self._current_id = 0

    def next_id(self) -> int:
        """
        Generate next unique request ID.
        """
        self._current_id += 1
        return self._current_id

class AgentClient:
    """
    Client for the Agent Protocol.
    Handles strict framing, envelope construction, and retries.
    """
    def __init__(self, server_ip: str, server_port: int):
        self.transport = TCPClient(server_ip, server_port)
        self.request_id_manager = RequestIdManager()

    def _send_with_retry(self, opcode: int, payload_bytes: bytes) -> Tuple[int, bytes, int, int]:
        """
        Internal method to send request and wait for valid response with retries.
        Returns: (status_code, response_payload_bytes, opcode, request_id)
        """
        request_id = self.request_id_manager.next_id()
        retries = 0
        current_timeout = INITIAL_RTO

        while retries <= MAX_RETRIES:
            try:
                # 1. Connect (or Reconnect)
                try:
                    self.transport.connect(timeout=current_timeout)
                except Exception as e:
                    logger.warning(f"Connection failed (attempt {retries+1}/{MAX_RETRIES+1}): {e}")
                    raise  # Trigger retry logic

                # 2. Build and Send Envelope
                # Flags=0 for basic Request/Response
                full_message = encode_message(opcode, 0, request_id, payload_bytes)
                
                start_time = time.time()
                self.transport.send_bytes(full_message)
                logger.debug(f"Sent ReqID={request_id} Op={opcode:#x} Len={len(payload_bytes)}")

                # 3. Receive Strict Framed Response
                # A. Read Header (Strict 12 bytes)
                header_data = self.transport.receive_exact(HEADER_SIZE)
                response_header = decode_header(header_data)

                # B. Validate Header
                if response_header.version != PROTOCOL_VERSION:
                    raise ValueError(f"Invalid Protocol Version: {response_header.version}")

                if response_header.payload_len > MAX_PAYLOAD_LEN:
                    raise ValueError(f"Payload too large: {response_header.payload_len}")

                # C. Read Payload (Strict payload_len bytes)
                response_payload_bytes = self.transport.receive_exact(response_header.payload_len)
                
                rtt_ms = (time.time() - start_time) * 1000

                # 4. Strict Request ID Validation
                if response_header.request_id != request_id:
                    logger.error(
                        f"ReqID Mismatch! Sent={request_id}, Recv={response_header.request_id}. "
                        "Dropping connection."
                    )
                    self.transport.close()
                    raise ConnectionError("Protocol Error: Request ID Mismatch")

                logger.debug(
                    f"Response Rx: ReqID={request_id} Op={response_header.opcode:#x} "
                    f"Len={response_header.payload_len} RTT={rtt_ms:.2f}ms"
                )
                
                # Note: Status code is usually inside the JSON payload, but we return raw bytes here.
                # We assume 200 implicit for transport success unless payload says otherwise.
                return (200, response_payload_bytes, response_header.opcode, response_header.request_id)

            except (ConnectionError, TimeoutError, socket.timeout) as e:
                # Retryable network errors
                logger.warning(f"Network Error (attempt {retries+1}): {e}")
                self.transport.close()
                retries += 1
                if retries > MAX_RETRIES:
                    raise TimeoutError(f"Max retries exceeded for ReqID={request_id}") from e
                
                # Exponential Backoff
                sleep_time = min(INITIAL_RTO * (2 ** (retries - 1)), MAX_RTO)
                time.sleep(sleep_time)
                current_timeout = min(current_timeout * 2, MAX_RTO)
            
            except Exception as e:
                # Non-retryable errors
                logger.error(f"Non-retryable Error: {e}")
                self.transport.close()
                raise e

        raise TimeoutError("Unreachable code reached")

    def send_request(self, opcode: int, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy/Generic API for JSON-only exchanges.
        """
        try:
            payload_bytes = json.dumps(payload_dict).encode("utf-8")
        except TypeError as e:
            raise ValueError(f"Payload not JSON serializable: {e}")

        _, resp_bytes, _, _ = self._send_with_retry(opcode, payload_bytes)
        
        try:
            response = json.loads(resp_bytes.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}, Data: {resp_bytes[:100]}")
            
        return response

    def list_files(self, path: str = ".", recursive: bool = False) -> list:
        """
        Execute LIST (0x05).
        Sends empty payload.
        Returns: List of filenames.
        """
        # Spec/User Note: Server ignores payload. Sending empty payload.
        payload = b""
        
        # Import opcodes locally if not in scope, or rely on constants
        from common.constants import OP_LIST
        
        _, resp_bytes, _, _ = self._send_with_retry(OP_LIST, payload)
        
        # Parse JSON response
        try:
            data = json.loads(resp_bytes.decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError(f"LIST response not JSON: {resp_bytes[:100]}")
            
        # Handle various response formats (list or dict with data)
        if isinstance(data, dict):
             status = data.get("status")
             if status and status >= 300:
                  raise ValueError(f"LIST failed: {status} {data.get('error')}")
             
             # Extract list from 'data' or 'files' if present, else return empty list or data itself
             return data.get("data", [])
        elif isinstance(data, list):
            return data
        else:
            return []

    def get_file(self, remote_path: str) -> bytes:
        """
        Execute GET (0x03).
        Returns: Raw file bytes on success.
        Raises: ValueError if server returns error JSON.
        """
        payload_dict = {"filename": remote_path}
        payload_bytes = json.dumps(payload_dict).encode("utf-8")
        
        from common.constants import OP_GET
        
        _, resp_bytes, _, _ = self._send_with_retry(OP_GET, payload_bytes)
        
        # Validation: Check if it's an error response (JSON with status >= 300)
        # Strategy: Peek if it looks like JSON. If so, check status.
        # This is a heuristic because file content could be JSON.
        # However, Agent Protocol usually wraps errors in specific JSON structure.
        try:
            # We only decode if it looks like it might be a small JSON error
            if len(resp_bytes) < 512: 
                decoded = resp_bytes.decode("utf-8")
                data = json.loads(decoded)
                if isinstance(data, dict) and "status" in data and data["status"] >= 300:
                     raise ValueError(f"GET failed: {data['status']} {data.get('error')}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Not JSON or not error JSON -> It's the file content
            pass
            
        return resp_bytes

    def append_file(self, remote_path: str, data: bytes) -> Dict[str, Any]:
        """
        Execute APPEND (0x04).
        Payload: JSON Metadata (UTF-8) + Raw Data.
        """
        # Construct mixed payload: JSON + Binary (No delimiter)
        meta_dict = {"filename": remote_path}
        # Compact JSON to be strictly compliant
        meta_json_bytes = json.dumps(meta_dict, separators=(',', ':')).encode('utf-8')
        
        payload = meta_json_bytes + data
        
        _, resp_bytes, _, _ = self._send_with_retry(OP_APPEND, payload)
        
        # Response should be standard JSON confirmation
        try:
            response = json.loads(resp_bytes.decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError(f"APPEND response not JSON: {resp_bytes[:100]}")
            
        if response.get("status", 200) >= 300:
             raise ValueError(f"APPEND failed: {response.get('status')} {response.get('error')}")
             
        return response

    def close(self):
        self.transport.close()
