"""
RUDP Server Transport Module (Day 8).
Handles UDP socket management, peer multiplexing, and isolated Reliable UDP state machines.
"""
import socket
import logging
import time
from typing import Dict, Tuple, Optional, Callable

from common.rudp_packet import RUDPPacket, ChecksumError, FLAG_ACK
from common.rudp_sender import RUDPSender
from common.rudp_receiver import RUDPReceiver
from common.constants import AGENT_SERVER_PORT, LOOPBACK_IP, MAX_RWND

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [RUDP-Server] %(message)s')
logger = logging.getLogger(__name__)

class RUDPConnection:
    """
    Virtual Connection Container encapsulating state for a specific (IP, Port) peer.
    Maintains isolated send and receive reliable states.
    """
    def __init__(self, addr: Tuple[str, int], 
                 send_raw_packet_cb: Callable[[bytes, Tuple[str, int]], None],
                 app_delivery_cb: Callable[[bytes, Tuple[str, int]], None]):
        self.addr = addr
        
        # We bind the global transport callbacks to this specific peer's address
        def bound_send_cb(data: bytes):
            send_raw_packet_cb(data, self.addr)
            
        def bound_app_cb(data: bytes):
            app_delivery_cb(data, self.addr)
            
        self.sender = RUDPSender(send_callback=bound_send_cb, window_size=MAX_RWND)
        self.receiver = RUDPReceiver(deliver_callback=bound_app_cb)
        self.last_seen = time.time()


class RUDPServerTransport:
    """
    Modular RUDP Server Transport component.
    Multiplexes multiple peers by (IP, Port) and ticks them safely in a single thread.
    """
    SOCKET_POLL_TIMEOUT = 0.05

    def __init__(self, port: int = AGENT_SERVER_PORT, bind_ip: str = LOOPBACK_IP, failure_engine=None):
        self.server_addr = (bind_ip, port)
        self.sock: Optional[socket.socket] = None
        self.connections: Dict[Tuple[str, int], RUDPConnection] = {}
        self.running = False
        self._app_message_handler: Optional[Callable[[bytes, Tuple[str, int]], None]] = None
        self.failure_engine = failure_engine

    def set_message_handler(self, handler: Callable[[bytes, Tuple[str, int]], None]) -> None:
        """
        Registers the application's callback for correctly reassembled payloads.
        The callback should expect (data: bytes, client_addr: tuple).
        """
        self._app_message_handler = handler

    def _deliver_to_app(self, data: bytes, client_addr: Tuple[str, int]) -> None:
        """Internal bridge from any connection's RUDPReceiver to the Application."""
        if self._app_message_handler:
            self._app_message_handler(data, client_addr)
        else:
            logger.warning(f"Received ordered data from {client_addr} but no app handler is set.")

    def send(self, data: bytes, request_id: int, client_addr: Tuple[str, int]) -> None:
        """
        Application-facing send method. 
        Routes data down to the specific client's isolated sender engine.
        """
        if client_addr not in self.connections:
            # We lazy-initialize connections just in case the server replies to a peer
            # that somehow wasn't instantiated (rare, but handleable).
            logger.info(f"Lazy-initializing RUDPConnection for targeted send to {client_addr}")
            self.connections[client_addr] = RUDPConnection(
                addr=client_addr,
                send_raw_packet_cb=self.send_raw_packet,
                app_delivery_cb=self._deliver_to_app
            )
            
        self.connections[client_addr].sender.enqueue_data(data, request_id, time.time())

    def start(self) -> None:
        """
        Main transport event loop (formerly 'serve()').
        Starts tracking connections and processing raw I/O.
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(self.server_addr)
            # Replaced setblocking(False) with strict poll timeout ticking after bind
            self.sock.settimeout(self.SOCKET_POLL_TIMEOUT)
            self.running = True
            logger.info(f"RUDP Transport listening on {self.server_addr}")

            self._receive_loop()
        except Exception as e:
            logger.critical(f"RUDP Transport startup failed: {e}")
        finally:
            self.close()

    def _receive_loop(self) -> None:
        """
        Background loop that acts as a multiplexer and global tick-generator.
        """
        while self.running:
            current_time = time.time()
            data = None
            addr = None
            
            try:
                # 65535 theoretical max UDP datagram
                data, addr = self.sock.recvfrom(65535)
            except (socket.timeout, BlockingIOError):
                # Timeout is expected to yield CPU and run tick engine
                pass
            except OSError as e:
                if not self.running:
                    break
                logger.error(f"Socket error in transport loop: {e}")
                time.sleep(self.SOCKET_POLL_TIMEOUT)
            except Exception as e:
                logger.exception(f"Unexpected error in receive loop: {e}")
                time.sleep(self.SOCKET_POLL_TIMEOUT)
                
            if data and addr:
                if self.failure_engine and self.failure_engine.should_drop_inbound():
                    # Silently discard the packet to simulate network loss
                    pass
                else:
                    self._handle_datagram(data, addr, current_time)
                
            # Broadcast the global timeout tick to all isolated sender connections
            self._tick_connections(time.time())

    def _handle_datagram(self, data: bytes, addr: Tuple[str, int], current_time: float) -> None:
        """
        Parse raw datagram, resolve target RUDPConnection, and demultiplex packet.
        """
        try:
            packet = RUDPPacket.unpack(data)
        except (ValueError, ChecksumError) as parse_error:
            logger.warning(f"Corrupted packet from {addr} received, dropping... Details: {parse_error}")
            return

        if addr not in self.connections:
            logger.info(f"New RUDP peer session: {addr}")
            self.connections[addr] = RUDPConnection(
                addr=addr,
                send_raw_packet_cb=self.send_raw_packet,
                app_delivery_cb=self._deliver_to_app
            )

        conn = self.connections[addr]
        conn.last_seen = current_time

        if packet.is_ack:
            logger.debug(f"RUDP [{addr}] ACK received: ack_num={packet.ack_num}, rwnd={packet.rwnd}")
            conn.sender.on_ack_received(packet.ack_num, packet.rwnd, current_time)
            
        if packet.has_data:
            logger.debug(f"RUDP [{addr}] DATA received: seq_num={packet.seq_num}, len={len(packet.payload)}")
            ack_num, rwnd, flags = conn.receiver.process_segment(packet)
            
            # Immediately acknowledge the data chunk back to this client
            logger.debug(f"RUDP [{addr}] Sending ACK: ack_num={ack_num}, rwnd={rwnd}")
            ack_packet = RUDPPacket(
                seq_num=0,
                ack_num=ack_num,
                flags=flags,
                rwnd=rwnd
            )
            self.send_raw_packet(ack_packet.pack(), addr)

    def _tick_connections(self, current_time: float) -> None:
        """
        Run the tick-engine evaluated RTO sweep on all active connections.
        """
        for conn in self.connections.values():
            try:
                conn.sender.check_timeouts(current_time)
            except Exception as e:
                logger.error(f"Error checking timeouts for {conn.addr}: {e}")

    def send_raw_packet(self, data: bytes, addr: Tuple[str, int]) -> None:
        """
        Directly send bytes to peer via UDP.
        """
        if not self.sock:
            return
        
        try:
            if self.failure_engine:
                self.failure_engine.apply_outbound(data, self.sock.sendto, addr)
            else:
                self.sock.sendto(data, addr)
        except Exception as e:
            if self.running:
                logger.error(f"Transport failed to send to {addr}: {e}")

    def close(self) -> None:
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
