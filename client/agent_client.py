"""
Agent Client Module.
Interacts with the Agent Server to submit tasks using the defined application envelope.
"""
import json
import time
import logging
from typing import Any, Dict, Optional, Tuple

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

    def _send_with_retry(self, opcode: int, payload_bytes: bytes) -> Dict[str, Any]:
        """
        Internal method to send request and wait for valid response with retries.
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
                # A. Read Header
                header_data = self.transport.receive_exact(HEADER_SIZE)
                response_header = decode_header(header_data)

                # B. Validate Header
                if response_header.version != PROTOCOL_VERSION:
                    raise ValueError(f"Invalid Protocol Version: {response_header.version}")

                if response_header.payload_len > MAX_PAYLOAD_LEN:
                    raise ValueError(f"Payload too large: {response_header.payload_len}")

                # C. Read Payload
                response_payload_bytes = self.transport.receive_exact(response_header.payload_len)
                
                rtt_ms = (time.time() - start_time) * 1000

                # 4. Strict Request ID Validation
                if response_header.request_id != request_id:
                    # Generic Protocol Error -> Close Connection & Fail (or Retry if idempotent)
                    # For Day-2, we treat this as a fatal mismatch for this connection.
                    logger.error(
                        f"ReqID Mismatch! Sent={request_id}, Recv={response_header.request_id}. "
                        "Dropping connection."
                    )
                    self.transport.close()
                    raise ConnectionError("Protocol Error: Request ID Mismatch")

                # 5. Parse JSON Payload
                try:
                    response_data = json.loads(response_payload_bytes.decode("utf-8"))
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON response: {e}")

                logger.info(
                    f"Success detected. ReqID={request_id} Status={response_data.get('status')} "
                    f"RTT={rtt_ms:.2f}ms"
                )
                
                return response_data

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
                # Nont-retryable errors (ValueError, ProtocolError, etc.)
                logger.error(f"Non-retryable Error: {e}")
                self.transport.close()
                raise e

        raise TimeoutError("Unreachable code reached")

    def send_request(self, opcode: int, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Public API to send a request.
        Encodes dict to JSON bytes and delegates to _send_with_retry.
        """
        try:
            payload_bytes = json.dumps(payload_dict).encode("utf-8")
        except TypeError as e:
            raise ValueError(f"Payload not JSON serializable: {e}")

        response = self._send_with_retry(opcode, payload_bytes)
        
        # Check Status Code
        status = response.get("status")
        if status is None:
             raise ValueError("Malformed response: missing 'status' field")

        # Map Errors
        if 200 <= status < 300:
            return response
        
        # Error statuses
        error_msg = response.get("error") or "Unknown Error"
        logger.error(f"Server Error {status}: {error_msg}")
        
        # In a real app, we might raise specific exceptions here
        # Return the response so caller can handle the error code
        return response

    def close(self):
        self.transport.close()

if __name__ == "__main__":
    # Internal component test (manual)
    import socket
    logging.basicConfig(level=logging.DEBUG)
    
    # Needs a running server to work
    try:
        client = AgentClient("127.0.0.1", 8080)
        # 0x05 = LIST
        resp = client.send_request(0x05, {})
        print("Response:", resp)
    except Exception as e:
        print("Test failed:", e)
