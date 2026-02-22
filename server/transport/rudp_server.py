"""
RUDP Server Transport Module (Day 6).
Handles UDP socket management, peer multiplexing, and strict envelope reassembly.
"""
import socket
import logging
import time
from typing import Dict, Tuple, Optional, Callable

from common.app_envelope import decode_header, HEADER_SIZE
from common.constants import AGENT_SERVER_PORT, LOOPBACK_IP

logger = logging.getLogger(__name__)

class ConnectionPeerState:
    """
    Maintains state for a single RUDP peer (client).
    Handles basic buffering and strict application envelope reassembly.
    """
    def __init__(self, addr: Tuple[str, int]):
        self.addr = addr
        self.receive_buffer = bytearray()
        self.last_seen = time.time()
        self.expected_payload_len: Optional[int] = None

    def append_data(self, data: bytes) -> Optional[bytes]:
        """
        Append received bytes to buffer and attempt to extract a full message.
        Returns the full message bytes (including header) if complete, else None.
        """
        self.receive_buffer.extend(data)
        self.last_seen = time.time()

        # Need at least HEADER_SIZE to know payload length
        if self.expected_payload_len is None:
            if len(self.receive_buffer) >= HEADER_SIZE:
                try:
                    header = decode_header(bytes(self.receive_buffer[:HEADER_SIZE]))
                    self.expected_payload_len = header.payload_len
                    logger.debug(f"Peer {self.addr}: Header parsed, expecting {self.expected_payload_len} bytes payload")
                except Exception as e:
                    logger.error(f"Peer {self.addr}: Invalid header received: {e}. Clearing buffer.")
                    self.receive_buffer.clear()
                    return None
            else:
                return None

        # Check if full payload received
        if len(self.receive_buffer) >= HEADER_SIZE + self.expected_payload_len:
            full_msg = bytes(self.receive_buffer[:HEADER_SIZE + self.expected_payload_len])
            # Keep remaining bytes for next message
            self.receive_buffer = self.receive_buffer[HEADER_SIZE + self.expected_payload_len:]
            self.expected_payload_len = None
            return full_msg

        return None

    def tick(self):
        """
        Placeholder for future retransmission/timeout logic.
        """
        pass

class RUDPServerTransport:
    """
    Modular RUDP Server Transport component.
    Multiplexes multiple peers by (IP, Port) and delivers full messages upward.
    """
    def __init__(self, port: int = AGENT_SERVER_PORT, bind_ip: str = LOOPBACK_IP):
        self.server_addr = (bind_ip, port)
        self.sock: Optional[socket.socket] = None
        self.peers: Dict[Tuple[str, int], ConnectionPeerState] = {}
        self.running = False

    def serve(self, on_message_cb: Callable[[str, bytes], bytes]):
        """
        Main transport event loop.
        on_message_cb(client_id, full_message_bytes) -> response_bytes
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.setblocking(False)
            self.sock.bind(self.server_addr)
            self.running = True
            logger.info(f"RUDP Transport listening on {self.server_addr}")

            while self.running:
                try:
                    data, addr = self.sock.recvfrom(2048)  # Sufficient for single UDP datagram
                    if not data:
                        continue
                    
                    self._handle_datagram(data, addr, on_message_cb)
                except BlockingIOError:
                    # Occurs when no data is available on non-blocking socket
                    time.sleep(0.01) # Avoid tight loop CPU spike
                    self._tick_peers()
                    continue
                except socket.error as e:
                    if self.running:
                        logger.error(f"Socket error in transport loop: {e}")
                    break
        except Exception as e:
            logger.critical(f"RUDP Transport startup failed: {e}")
        finally:
            self.close()

    def _handle_datagram(self, data: bytes, addr: Tuple[str, int], on_message_cb: Callable):
        """
        Route incoming datagram to peer-specific reassembly buffer.
        """
        if addr not in self.peers:
            logger.info(f"New RUDP peer session: {addr}")
            self.peers[addr] = ConnectionPeerState(addr)

        peer = self.peers[addr]
        full_msg = peer.append_data(data)

        if full_msg:
            # client_id is the string representation of Source (IP, Port)
            client_id = f"{addr[0]}:{addr[1]}"
            logger.info(f"Full message reassembled from {client_id}. Delivering.")
            
            # Execute application logic via callback
            response = on_message_cb(client_id, full_msg)
            
            if response:
                logger.info(f"Sending response back to {client_id} ({len(response)} bytes).")
                self.send_bytes(addr, response)

    def _tick_peers(self):
        """
        Hooks for future reliability maintenance (timeouts, retransmits).
        """
        for addr, peer in list(self.peers.items()):
            peer.tick()
            # Future: Cleanup inactive peers (e.g., if last_seen > 30s)

    def send_bytes(self, addr: Tuple[str, int], data: bytes):
        """
        Directly send bytes to peer via UDP.
        (Layered above standard socket.sendto)
        """
        if not self.sock:
            return
        
        try:
            self.sock.sendto(data, addr)
        except Exception as e:
            logger.error(f"Transport failed to send to {addr}: {e}")

    def close(self):
        """
        Graceful shutdown: stop loop and close socket.
        """
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
        logger.info("RUDP Transport shutdown complete.")
