"""
TCP Server Implementation (Day 1 Skeleton).
Follows System Specification and Day 1 constraints.
"""
import socket
import struct
import logging
import sys
from typing import Optional, Callable

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

class TCPServerTransport:
    """
    Reusable TCP Server Transport.
    Provides generic socket primitives for the AgentServer.
    """
    is_async = False  # Strict boolean flag for AgentServer polymorphic branching
    
    def __init__(self, port: int = AGENT_SERVER_PORT, bind_ip: str = LOOPBACK_IP):
        self.server_addr = (bind_ip, port)
        self.sock: Optional[socket.socket] = None
        self.active_conns: dict[tuple, socket.socket] = {}

    def start(self):
        """Bind and listen."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(self.server_addr)
            self.sock.listen(5)
            logger.info(f"TCP Server listening on {self.server_addr}")
        except Exception as e:
            logger.critical(f"Failed to bind TCP server: {e}")
            raise

    def accept(self) -> tuple[socket.socket, tuple]:
        """Accept a new connection."""
        if not self.sock:
            raise ConnectionError("Server not started")
        conn, addr = self.sock.accept()
        self.active_conns[addr] = conn
        return conn, addr

    def receive_exact(self, conn: socket.socket, nbytes: int) -> bytes:
        """Read exactly nbytes from a specific connection."""
        buf = bytearray()
        while len(buf) < nbytes:
            chunk = conn.recv(nbytes - len(buf))
            if not chunk:
                raise ConnectionError("Connection closed before reading complete message")
            buf.extend(chunk)
        return bytes(buf)

    def send_bytes(self, conn: socket.socket, data: bytes):
        """Send raw bytes to a specific connection. (Legacy compatibility)"""
        conn.sendall(data)
        
    def send(self, data: bytes, request_id: int = 0, client_addr: tuple = None) -> None:
        """
        Polymorphic send() matching the RUDPServerTransport signature.
        Locates the specific TCP socket bound to client_addr and pushes the response.
        """
        if not client_addr or client_addr not in self.active_conns:
            logger.error(f"Cannot map TCP response: Unknown client_addr {client_addr}")
            return
            
        conn = self.active_conns[client_addr]
        try:
            self.send_bytes(conn, data)
        except Exception as e:
            logger.error(f"Failed to send TCP response to {client_addr}: {e}")

    def close(self):
        """Stop the server."""
        if self.sock:
            self.sock.close()

# Legacy runner removed in favor of AgentServer-driven architecture

