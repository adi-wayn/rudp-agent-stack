"""
TCP Client Transport.
Implements a Day-1 TCP CLIENT skeleton for the PING/PONG echo test.
"""
import socket
import logging
import sys
from typing import Optional

# Import envelope utilities
try:
    from common.app_envelope import decode_header, encode_message, HEADER_SIZE # type: ignore
except ImportError:
    # This might happen if running from inside client/transport without setting PYTHONPATH
    # But we assume the environment is set up correctly as per instructions
    raise

# Import constants
try:
    from common.constants import AGENT_SERVER_PORT, LOOPBACK_IP, MAX_PAYLOAD_LEN # type: ignore
except ImportError:
    # Safe defaults if constants are missing/renamed (though instructions say they exist)
    AGENT_SERVER_PORT = 8080
    LOOPBACK_IP = "127.0.0.1"
    MAX_PAYLOAD_LEN = 1024 * 1024

# Configuration
BASIC_LOG_FORMAT = "[TCP-Client] %(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=BASIC_LOG_FORMAT)
logger = logging.getLogger("TCPClient")

# Day 1 Opcodes (Local Placeholders)
OP_PING = 0xFF
OP_PONG = 0xFE

def read_exact(sock: socket.socket, nbytes: int) -> bytes:
    """
    Read exactly nbytes from the socket.
    Raises ConnectionError if the socket closes before reading all bytes.
    """
    data = bytearray()
    while len(data) < nbytes:
        try:
            chunk = sock.recv(nbytes - len(data))
            if not chunk:
                raise ConnectionError(f"Connection closed mid-read. Expected {nbytes}, got {len(data)}")
            data.extend(chunk)
        except socket.error as e:
            raise ConnectionError(f"Socket error during read: {e}") from e
    return bytes(data)

def run_client():
    """
    Main client execution flow:
    1. Connect
    2. PING
    3. PONG
    """
    server_addr = (LOOPBACK_IP, AGENT_SERVER_PORT)
    sock: Optional[socket.socket] = None

    try:
        # 1) Connect
        logger.info(f"Connecting to {server_addr}...")
        try:
            sock = socket.create_connection(server_addr, timeout=5.0)
        except socket.error as e:
            logger.error(f"Failed to connect: {e}")
            raise

        logger.info("Connected.")

        # 2) Build PING message
        payload = b"PING Payload Data"
        if len(payload) > MAX_PAYLOAD_LEN:
             raise ValueError("Payload exceeds max limit")

        logger.info(f"Sending PING: opcode={OP_PING:#x}, payload_len={len(payload)}")
        
        # Use existing project envelope utility
        # Note: app_envelope.encode_message signature: (opcode, flags, request_id, payload)
        full_message = encode_message(OP_PING, 0, 12345, payload)

        # 3) Send
        sock.sendall(full_message)

        # 4) Receive Framed Response
        
        # A. Read Header
        header_data = read_exact(sock, HEADER_SIZE)
        
        # B. Decode Header
        header = decode_header(header_data)
        
        # C. Read Payload
        # Validate payload length for safety (optional but good robustness)
        if header.payload_len > MAX_PAYLOAD_LEN:
             raise ValueError(f"Response payload too large: {header.payload_len}")

        payload_data = read_exact(sock, header.payload_len)
        
        # 5) Print Summary
        logger.info(f"Received Response: opcode={header.opcode:#x}, payload_len={header.payload_len}")
        
        summary = (
            f"\n--- Parsed Response ---\n"
            f"Opcode:      {header.opcode:#x}\n"
            f"Payload Len: {header.payload_len}\n"
            f"Request ID:  {header.request_id}\n"
            f"Payload:     {payload_data.decode(errors='replace')}\n"
            f"-----------------------"
        )
        print(summary)
        
        # Logic Check
        if header.opcode == OP_PONG:
            logger.info("Test PASSED: Received PONG.")
        else:
            logger.warning(f"Test UNCERTAIN: Expected PONG ({OP_PONG:#x}), got {header.opcode:#x}")

    except Exception as e:
        logger.error(f"Client error: {e}")
        # In a real app we might re-raise, but for a test script we just log
        sys.exit(1)
    finally:
        if sock:
            try:
                sock.close()
                logger.info("Socket closed.")
            except Exception as e:
                logger.error(f"Error closing socket: {e}")

if __name__ == "__main__":
    # Smoke run instructions:
    # Ensure PYTHONPATH includes the project root
    # python -m client.transport.tcp_client
    run_client()
