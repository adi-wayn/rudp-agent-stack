"""
Agent Client Module.
Interacts with the Agent Server to submit tasks using the defined application envelope.
"""
import json
import time
import logging
import socket
from typing import Any, Dict, Optional, Tuple

from common.constants import OP_GET, OP_APPEND, OP_LIST
from common.mixed_mode_io import MixedModeEncoder, MixedModeDecoder

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
        Request Payload: JSON {}
        Response Payload: JSON
        Returns: List of filenames (or detailed list if server returns it).
        """
        # Day 4: Send strict JSON payload "{}"
        payload = b"{}"
        
        _, resp_bytes, _, _ = self._send_with_retry(OP_LIST, payload)
        
        # Parse JSON response
        try:
            data = json.loads(resp_bytes.decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError(f"LIST response not JSON: {resp_bytes[:100]}")
            
        # Handle various response formats
        if isinstance(data, dict):
             # Check for error status
             status = data.get("status")
             if status and status >= 300:
                  raise ValueError(f"LIST failed: {status} {data.get('error')}")
             
             # Day 4: Server returns { "files": [...] }
             if "files" in data:
                 return data["files"]
                 
             return data.get("data", [])
        elif isinstance(data, list):
            return data
        else:
            return []

    def get_file(self, remote_path: str) -> bytes:
        """
        Execute GET (0x03).
        Request: JSON {"filename": ...}
        Response: 
            - 200 OK: Mixed Mode [Len][Meta][Binary]
            - Error: JSON Only
        Returns: Raw file bytes on success.
        Raises: ValueError on error response.
        """
        payload_dict = {"filename": remote_path}
        payload_bytes = json.dumps(payload_dict).encode("utf-8")
        
        _, resp_bytes, _, _ = self._send_with_retry(OP_GET, payload_bytes)
        
        # Try Decoding as Mixed Mode first (Success Case)
        try:
            meta, binary = MixedModeDecoder.decode(resp_bytes)
            # Check status inside meta
            status = meta.get("status", 200)
            if status >= 300:
                raise ValueError(f"GET failed (Mixed): {status} {meta.get('error')}")
            return binary
            
        except ValueError:
            # Fallback: Try Pure JSON (Error Case)
            try:
                data = json.loads(resp_bytes.decode("utf-8"))
                status = data.get("status")
                if status and status >= 300:
                    raise ValueError(f"GET failed: {status} {data.get('error')}")
                # If valid JSON but no binary and no error? Empty file?
                # or Day 4 specific: binary is mandatory for success in Mixed Mode response.
                # If we are here, it wasn't mixed mode.
                # If unexpected format:
                raise ValueError(f"Unexpected GET response format: {resp_bytes[:100]}")
            except json.JSONDecodeError:
                pass
            
            # If neither, fail
            raise ValueError(f"Invalid GET response format (neither Mixed nor JSON): {resp_bytes[:100]}")

    def append_file(self, remote_path: str, data: bytes) -> Dict[str, Any]:
        """
        Execute APPEND (0x04).
        Request: Mixed Mode [Meta][Binary]
        Response: JSON
        """
        # Construct mixed payload using Common Utility
        payload = MixedModeEncoder.encode({"filename": remote_path}, data)
        
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
