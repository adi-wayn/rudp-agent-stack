"""
Day-2 TCP Server Shim.
Integrates the Day-1 TCP Transport loop with the Day-2 AgentServer logic.
Used for validating the Day-2 Client.
"""
import socket
import logging
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from common.app_envelope import decode_header, HEADER_SIZE
from common.constants import AGENT_SERVER_PORT, LOOPBACK_IP
from server.agent_server import AgentServer

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [Day2-Server] %(message)s',
    filename='server_shim.log',
    filemode='w'
)
# Add console handler as well just in case
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)
logger = logging.getLogger("Day2ServerShim")

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

def handle_client(conn: socket.socket, addr: tuple, agent: AgentServer):
    """
    Handle a single client connection stream using AgentServer.
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

            # 2. Decode Header to get payload length
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

            # 4. Construct Full Packet for AgentServer
            full_packet = header_bytes + payload
            
            # 5. Process via Agent Logic
            response_bytes = agent.process_request(client_id, full_packet)
            
            if response_bytes:
                conn.sendall(response_bytes)
                logger.info(f"Sent response to {client_id} (len={len(response_bytes)})")
            else:
                logger.warning(f"AgentServer returned no response for {client_id}")

    except Exception as e:
        logger.error(f"Unexpected error handling client {client_id}: {e}")
    finally:
        conn.close()

def run_server():
    """
    Main TCP Server Loop.
    """
    # Create Sandbox for testing
    sandbox_dir = os.path.join(os.getcwd(), "sandbox_test")
    os.makedirs(sandbox_dir, exist_ok=True)
    
    agent = AgentServer(sandbox_root=sandbox_dir)
    
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_sock.bind((LOOPBACK_IP, AGENT_SERVER_PORT))
        server_sock.listen(5)
        logger.info(f"Day-2 TCP Server listening on {LOOPBACK_IP}:{AGENT_SERVER_PORT}")
        
        while True:
            conn, addr = server_sock.accept()
            handle_client(conn, addr, agent)
            
    except KeyboardInterrupt:
        logger.info("Server stopping...")
    except Exception as e:
        logger.critical(f"Server crashed: {e}")
    finally:
        server_sock.close()

if __name__ == "__main__":
    run_server()
