import socket
import threading
import logging
import time
from typing import Optional, Callable

from common.rudp_packet import RUDPPacket, ChecksumError, FLAG_ACK
from common.rudp_sender import RUDPSender
from common.rudp_receiver import RUDPReceiver
from common.constants import MAX_RWND

logger = logging.getLogger(__name__)


class RUDPClientTransport:
    """
    Client-side Reliable UDP I/O Adapter (Layer 4 boundary).
    
    Integrates RUDPSender and RUDPReceiver to provide a reliable, pipelined
    application-layer interface over a raw UDP socket.
    """
    
    # Tick rate for non-blocking recv loops
    SOCKET_POLL_TIMEOUT = 0.05
    is_async = True

    def __init__(self, server_host: str, server_port: int, client_ip: str = "NOT_SET", failure_engine=None) -> None:
        """
        Initializes the client transport, sets up the socket, and instantiates
        the Sender and Receiver engines.
        """
        self.server_host = server_host
        self.server_port = server_port
        self.client_ip = client_ip
        self.failure_engine = failure_engine
        
        # Create and bind UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.client_ip != "NOT_SET":
            logger.info(f"Binding UDP socket to {self.client_ip}:0")
            self.socket.bind((self.client_ip, 0))
            
        self.socket.connect((self.server_host, self.server_port))
        
        self._running = False
        self._receive_thread: Optional[threading.Thread] = None
        
        # Application-layer callback
        self._app_message_handler: Optional[Callable[[bytes], None]] = None
        
        # Instantiate RUDP Engines
        self.sender = RUDPSender(send_callback=self.send_raw_packet, window_size=MAX_RWND)
        self.receiver = RUDPReceiver(deliver_callback=self._deliver_to_app)

    def set_message_handler(self, handler: Callable[[bytes], None]) -> None:
        """Registers the application's callback for correctly reassembled payloads."""
        self._app_message_handler = handler

    def _deliver_to_app(self, data: bytes) -> None:
        """Internal bridge from RUDPReceiver to the Application."""
        if self._app_message_handler:
            self._app_message_handler(data)
        else:
            logger.warning("Received ordered data but no app message handler is set.")

    def send(self, data: bytes, request_id: int) -> None:
        """
        Application-facing send method. Pushes data into the sender's queue.
        """
        self.sender.enqueue_data(data, request_id, time.time())

    def connect(self, timeout: float = 5.0) -> None:
        """Polymorphic alias to start()"""
        self.start()

    def start(self) -> None:
        """
        Starts the background receive loop thread as a daemon.
        """
        if self._running:
            return
            
        self._running = True
        
        # Enforce explicitly here before loop
        self.socket.settimeout(self.SOCKET_POLL_TIMEOUT)
        
        self._receive_thread = threading.Thread(
            target=self._receive_loop,
            name="RUDPClient-ReceiveLoop",
            daemon=True
        )
        self._receive_thread.start()
        logger.info(f"RUDPClientTransport started, bound to {self.server_host}:{self.server_port}")

    def close(self) -> None:
        """
        Signals the receive loop to terminate and closes the socket.
        """
        self._running = False
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
            
        self.socket.close()
        
        if self._receive_thread and self._receive_thread.is_alive():
            self._receive_thread.join(timeout=1.0)
            
        logger.info("RUDPClientTransport closed.")

    def send_raw_packet(self, packet: bytes) -> None:
        """
        Serializes and transmits raw bytes (an encoded payload or ACK) to the connected endpoint.
        """
        try:
            if self.failure_engine:
                self.failure_engine.apply_outbound(packet, self.socket.send)
            else:
                self.socket.send(packet)
        except OSError as e:
            if not self._running:
                return
            logger.error(f"Failed to send RUDP packet: {e}")

    def _receive_loop(self) -> None:
        """
        Background loop that relentlessly reads from the socket, reconstructs
        RUDP packets, routes them to Sender/Receiver, and ticks the Sender's RTO timer.
        """
        while self._running:
            current_time = time.time()
            data = None
            
            try:
                # Read up to the maximum theoretical UDP payload size
                data = self.socket.recv(65535)
            except (socket.timeout, BlockingIOError):
                # Expected timeout, act as a tick generator. Proceed to end of loop.
                pass
            except OSError as e:
                # Expected behaviour during shutdown when socket is closed
                if not self._running:
                    break
                logger.error(f"Socket error in receive loop: {e}")
                time.sleep(self.SOCKET_POLL_TIMEOUT)  # Prevent tight loop on error
            except Exception as e:
                logger.exception(f"Unexpected error in receive loop: {e}")
                time.sleep(self.SOCKET_POLL_TIMEOUT)
                
            # If we successfully read data, parse and route it
            if data:
                if self.failure_engine and self.failure_engine.should_drop_inbound():
                    # Silently discard the packet to simulate loss (pre-parsing)
                    pass
                else:
                    try:
                        packet = RUDPPacket.unpack(data)
                        self.on_packet_received(packet, current_time)
                    except (ValueError, ChecksumError) as parse_error:
                        logger.warning(f"Corrupted packet received, dropping... Details: {parse_error}")

            # Tick-based retransmission engine evaluation at the end of EVERY loop iteration
            try:
                self.sender.check_timeouts(time.time())
            except Exception as e:
                logger.error(f"Error checking timeouts: {e}")

    def on_packet_received(self, packet: RUDPPacket, current_time: float) -> None:
        """
        Demultiplexes valid traffic between the Sender and Receiver.
        """
        if packet.is_ack:
            # Route to sender to clear unacked buffers
            self.sender.on_ack_received(packet.ack_num, packet.rwnd, current_time)
            
        if packet.has_data:
            # Route to receiver to process payload
            ack_num, rwnd, flags = self.receiver.process_segment(packet)
            
            # Immediately generate and send the corresponding ACK
            ack_packet = RUDPPacket(
                seq_num=0,
                ack_num=ack_num,
                flags=flags,
                rwnd=rwnd
            )
            self.send_raw_packet(ack_packet.pack())
