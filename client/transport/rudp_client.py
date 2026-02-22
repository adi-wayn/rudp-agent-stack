import socket
import threading
import logging
from typing import Optional

from common.rudp_packet import RUDPPacket, ChecksumError

logger = logging.getLogger(__name__)

class RUDPClientTransport:
    """
    Client-side Reliable UDP I/O Adapter (Layer 4 boundary).
    
    This class handles the raw UDP socket operations, utilizing the OS-level
    connect() pattern for UDP to enforce a point-to-point relationship with
    the server. It provides framing boundaries by interpreting byte streams
    into RUDPPacket instances, and securely drops any packets with framing
    or checksum errors without disrupting the client application.
    """

    def __init__(self, server_host: str, server_port: int) -> None:
        """
        Initializes the client transport and applies the UDP connect() pattern.
        """
        self.server_host = server_host
        self.server_port = server_port
        
        # Create a UDP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # OS-Level Socket Binding (UDP connect trick)
        # Using connect() on a UDP socket associates the socket with the target
        # tuple at the kernel level. This allows standard send()/recv() calls
        # instead of sendto()/recvfrom(), and cleanly drops spoofed/unassociated packets.
        self.socket.connect((self.server_host, self.server_port))
        
        self._running = False
        self._receive_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """
        Starts the background receive loop thread as a daemon.
        """
        if self._running:
            return
            
        self._running = True
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
            pass  # Socket might already be closed or not fully connected
            
        self.socket.close()
        
        if self._receive_thread and self._receive_thread.is_alive():
            self._receive_thread.join(timeout=1.0)
            
        logger.info("RUDPClientTransport closed.")

    def send_raw_packet(self, packet: RUDPPacket) -> None:
        """
        Serializes and transmits the RUDP packet to the connected endpoint.
        """
        try:
            data = packet.pack()
            # Since connect() was called, we use standard send()
            self.socket.send(data)
        except Exception as e:
            logger.error(f"Failed to send RUDP packet: {e}")
            raise

    def _receive_loop(self) -> None:
        """
        Background loop that relentlessly reads from the socket, reconstructs
        RUDP packets, and filters corrupted data.
        """
        while self._running:
            try:
                # Read up to the maximum theoretical UDP payload size
                data = self.socket.recv(65535)
                if not data:
                    continue  # Depending on OS, zero bytes might mean closed connection, but we loop.
                    
                # Explicitly catch framing/checksum errors to drop them cleanly
                try:
                    packet = RUDPPacket.unpack(data)
                except (ValueError, ChecksumError) as parse_error:
                    logger.warning(f"Corrupted packet received, dropping... Details: {parse_error}")
                    continue  # Simulate network loss by ignoring bad packets

                # Route successfully parsed packets up the stack
                self.on_packet_received(packet)
                
            except OSError as e:
                if not self._running:
                    # Ignored: expected behaviour during shutdown when socket is closed
                    break
                logger.error(f"Socket error in receive loop: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error in receive loop: {e}")

    def on_packet_received(self, packet: RUDPPacket) -> None:
        """
        State Machine Stub.
        
        For Day 6, this simply logs the valid packet's sequence number and flags.
        For Day 8, reliable state algorithms (ACK processing, sequence tracking)
        will be injected here.
        """
        logger.debug(f"[STUB] Packet Received: Seq={packet.seq_num}, Flags={packet.flags}, rwnd={packet.rwnd}")
