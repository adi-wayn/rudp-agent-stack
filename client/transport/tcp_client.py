"""
TCP Client Transport.
Implements a Day-1 TCP CLIENT skeleton for the PING/PONG echo test.
Refactored for Day-2 to provide a reusable TCPClient class.
"""
import socket
import logging
import sys
import time
from typing import Optional

# Import envelope utilities
from common.app_envelope import decode_header, encode_message, HEADER_SIZE

# Import constants
from common.constants import AGENT_SERVER_PORT, LOOPBACK_IP, MAX_PAYLOAD_LEN

# Configuration
BASIC_LOG_FORMAT = "[TCP-Client] %(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=BASIC_LOG_FORMAT)
logger = logging.getLogger("TCPClient")

# Day 1 Opcodes (Local Placeholders)
OP_PING = 0xFF
OP_PONG = 0xFE

class TCPClient:
    """
    Reusable TCP Client Wrapper.
    """
    def __init__(self, server_ip: str = LOOPBACK_IP, server_port: int = AGENT_SERVER_PORT):
        self.server_addr = (server_ip, server_port)
        self.sock: Optional[socket.socket] = None

    def connect(self, timeout: float = 5.0):
        """
        Establish TCP connection.
        """
        logger.info(f"Connecting to {self.server_addr}...")
        try:
            self.sock = socket.create_connection(self.server_addr, timeout=timeout)
            logger.info("Connected.")
        except socket.error as e:
            logger.error(f"Failed to connect: {e}")
            raise ConnectionError(f"Failed to connect to {self.server_addr}") from e

    def send_bytes(self, data: bytes):
        """
        Send raw bytes.
        """
        if not self.sock:
            raise ConnectionError("Not connected")
        try:
            self.sock.sendall(data)
        except socket.error as e:
            raise ConnectionError(f"Socket error during send: {e}") from e

    def receive_exact(self, nbytes: int) -> bytes:
        """
        Read exactly nbytes from the socket.
        Raises ConnectionError if the socket closes before reading all bytes.
        """
        if not self.sock:
            raise ConnectionError("Not connected")
        
        data = bytearray()
        while len(data) < nbytes:
            try:
                chunk = self.sock.recv(nbytes - len(data))
                if not chunk:
                    raise ConnectionError(f"Connection closed mid-read. Expected {nbytes}, got {len(data)}")
                data.extend(chunk)
            except socket.error as e:
                raise ConnectionError(f"Socket error during read: {e}") from e
        return bytes(data)

    def close(self):
        """
        Close the connection safely.
        """
        if self.sock:
            try:
                self.sock.close()
                logger.info("Socket closed.")
            except Exception as e:
                logger.error(f"Error closing socket: {e}")
            finally:
                self.sock = None

    def receive_response(self) -> tuple[int, int, int, bytes]:
        """
        Receive and decode a full application envelope.
        Returns: (opcode, flags, request_id, payload_bytes)
        helper method useful for simple interactions.
        """
        # A. Read Header
        header_data = self.receive_exact(HEADER_SIZE)
        
        # B. Decode Header
        header = decode_header(header_data)
        
        # C. Read Payload
        if header.payload_len > MAX_PAYLOAD_LEN:
             raise ValueError(f"Response payload too large: {header.payload_len}")

        payload_data = self.receive_exact(header.payload_len)
        
        return header.opcode, header.flags, header.request_id, payload_data

def run_client():
    """
    Main client execution flow (Day 1 PING/PONG Compatibility).
    """
    client = TCPClient()
    
    try:
        # 1) Connect
        client.connect()

        # 2) Build PING message
        payload = b"PING Payload Data"
        logger.info(f"Sending PING: opcode={OP_PING:#x}, payload_len={len(payload)}")
        
        full_message = encode_message(OP_PING, 0, 12345, payload)

        # 3) Send
        client.send_bytes(full_message)

        # 4) Receive Framed Response
        opcode, _, request_id, payload_data = client.receive_response()
        
        # 5) Print Summary
        logger.info(f"Received Response: opcode={opcode:#x}, payload_len={len(payload_data)}")
        
        summary = (
            f"\n--- Parsed Response ---\n"
            f"Opcode:      {opcode:#x}\n"
            f"Payload Len: {len(payload_data)}\n"
            f"Request ID:  {request_id}\n"
            f"Payload:     {payload_data.decode(errors='replace')}\n"
            f"-----------------------"
        )
        print(summary)
        
        # Logic Check
        if opcode == OP_PONG:
            logger.info("Test PASSED: Received PONG.")
        else:
            logger.warning(f"Test UNCERTAIN: Expected PONG ({OP_PONG:#x}), got {opcode:#x}")

    except Exception as e:
        logger.error(f"Client error: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    run_client()
