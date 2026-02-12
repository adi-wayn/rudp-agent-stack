"""
TCP Server Implementation (Day 1 Skeleton).
Follows System Specification and Day 1 constraints.
"""
import socket
import struct
import logging
import sys
from typing import Optional

# Adjust path to include project root for imports if needed
# (Assuming running as module: python -m server.transport.tcp_server)

from common.app_envelope import decode_header, encode_message, HEADER_SIZE
from common.constants import AGENT_SERVER_PORT, MAX_PAYLOAD_LEN, LOOPBACK_IP

# Configure Logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [TCP-Server] %(message)s')
logger = logging.getLogger(__name__)

# Day 1 Opcode Placeholders (Local definition to avoid modifying common/constants.py)
OP_PING = 0xFF
OP_PONG = 0xFE

def read_exact(sock: socket.socket, nbytes: int) -> bytes:
    """
    Helper to read exactly nbytes from the socket.
    Raises ConnectionError if connection closes prematurely.
    """
    buf = bytearray()
    while len(buf) < nbytes:
        chunk = sock.recv(nbytes - len(buf))
        if not chunk:
            raise ConnectionError("Connection closed before reading complete message")
        buf.extend(chunk)
    return bytes(buf)

def handle_client(conn: socket.socket, addr: tuple):
    """
    Handle a single client connection stream.
    """
    client_id = f"{addr[0]}:{addr[1]}"
    logger.info(f"Accepted connection from {client_id}")

    try:
        while True:
            # 1. Read Fixed Header (12 bytes)
            try:
                header_bytes = read_exact(conn, HEADER_SIZE)
            except ConnectionError:
                logger.info(f"Client {client_id} disconnected.")
                break

            # 2. Decode Header
            try:
                header = decode_header(header_bytes)
            except ValueError as e:
                logger.error(f"Header validation failed for {client_id}: {e}")
                break

            # 3. Read Payload
            try:
                payload = read_exact(conn, header.payload_len)
            except ConnectionError:
                logger.error(f"Client {client_id} disconnected during payload read.")
                break

            # Log Request
            logger.debug(f"Req: client={client_id} op={header.opcode} req_id={header.request_id} len={header.payload_len}")

            # 4. Dispatch (Day 1: Minimal PING/PONG)
            if header.opcode == OP_PING:
                # Echo payload in PONG
                response_payload = payload
                response_flags = 0 # No specific flags
                
                # Encode response
                response_data = encode_message(OP_PONG, response_flags, header.request_id, response_payload)
                
                # Send strictly
                conn.sendall(response_data)
                logger.info(f"Sent PONG to {client_id} (req_id={header.request_id})")
            
            else:
                # Unknown opcode for Day 1 -> Close or Error
                # Per spec/prompt: "respond with a structured error... OR close gracefully"
                logger.warning(f"Unknown Opcode {header.opcode} from {client_id}. Closing connection.")
                break

    except Exception as e:
        logger.error(f"Unexpected error handling client {client_id}: {e}")
    finally:
        conn.close()
        logger.info(f"Connection closed for {client_id}")

def run_server(port: int = AGENT_SERVER_PORT):
    """
    Main TCP Server Loop.
    """
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_sock.bind((LOOPBACK_IP, port))
        server_sock.listen(5)
        logger.info(f"TCP Server listening on {LOOPBACK_IP}:{port}")
        
        while True:
            conn, addr = server_sock.accept()
            # For Day 1, sequential handling (blocking) is acceptable/requested ("simple loop")
            # But "accept connection, loop" implies we might block other clients if we don't thread.
            # "Keep a simple single-threaded accept loop for Day 1" -> sequential is fine.
            handle_client(conn, addr)
            
    except KeyboardInterrupt:
        logger.info("Server stopping...")
    except Exception as e:
        logger.critical(f"Server crashed: {e}")
    finally:
        server_sock.close()

if __name__ == "__main__":
    # Smoke run instruction:
    # python -m server.transport.tcp_server
    run_server()
