"""
DHCP Client Module.
Handles IP acquisition from the DHCP server following the DORA handshake.
"""
import socket
import json
import logging
import random
import time
from typing import Optional, Tuple
from common.dhcp_packet import DHCPPacket
from common.constants import DHCP_SERVER_PORT, DHCP_CLIENT_PORT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("DHCPClient")

class DHCPClient:
    """
    Client for the Custom DHCP protocol (Day 11).
    Implements DISCOVER -> OFFER -> REQUEST -> ACK flow (DORA).
    """
    
    # States
    INIT = "INIT"
    SELECTING = "SELECTING"
    REQUESTING = "REQUESTING"
    BOUND = "BOUND"

    def __init__(self, mac_address: str, server_port: int = DHCP_SERVER_PORT, client_port: int = DHCP_CLIENT_PORT):
        """
        Initialize DHCP client.
        :param mac_address: Unique hardware identifier for the client.
        :param server_port: Port of the DHCPServer (default 67)
        :param client_port: Port to bind to (default 68)
        """
        self.mac_address = mac_address
        self.server_port = server_port
        self.client_port = client_port
        self.state = self.INIT
        
        # Lease Metadata
        self.assigned_ip: Optional[str] = None
        self.lease_time: int = 0
        self.lease_expiry: float = 0.0
        
        # Socket setup
        self.sock: Optional[socket.socket] = None
        
        # Retry constants
        self.MAX_RETRIES_PER_STAGE = 5
        self.INITIAL_TIMEOUT = 0.5  # 500ms
        self.FALLBACK_THRESHOLD = 2   # Attempts before switching to 127.0.0.1
        self.SERVER_FALLBACK_IP = "127.0.0.1"

    def _init_socket(self) -> None:
        """Initialize and bind the UDP socket for DHCP."""
        if self.sock:
            self.sock.close()
            
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        try:
            # Bind to all interfaces on configured client port
            self.sock.bind(("", self.client_port))
            logger.debug(f"Socket bound to port {self.client_port}")
        except PermissionError:
            logger.warning(f"Could not bind to port {self.client_port}. Falling back to ephemeral port.")
            self.sock.bind(("", 0))

    def _send_packet(self, packet: DHCPPacket, dest_ip: str = "255.255.255.255") -> None:
        """Serialize and send packet to the server."""
        if not self.sock:
            raise RuntimeError("Socket not initialized")
            
        data = packet.to_bytes()
        self.sock.sendto(data, (dest_ip, self.server_port))
        logger.debug(f"Sent {packet.message_type} (XID: {packet.xid}) to {dest_ip}:{self.server_port}")

    def _receive_packet(self, timeout: float) -> Optional[DHCPPacket]:
        """Wait for a DHCP packet within the timeout."""
        if not self.sock:
            return None
            
        self.sock.settimeout(timeout)
        try:
            data, addr = self.sock.recvfrom(2048)
            packet = DHCPPacket.from_bytes(data)
            logger.debug(f"Received {packet.message_type} (XID: {packet.xid}) from {addr}")
            return packet
        except (socket.timeout, ValueError) as e:
            if isinstance(e, ValueError):
                logger.warning(f"Malformed packet received: {e}")
            return None

    def acquire_lease(self) -> bool:
        """
        Orchestrate the DORA flow to acquire an IP lease.
        :return: True if successful, False otherwise.
        """
        try:
            self._init_socket()
            self.state = self.INIT
            xid = random.getrandbits(32)
            
            # --- SELECTING Stage (DISCOVER -> OFFER) ---
            offered_ip = self._perform_selecting(xid)
            if not offered_ip:
                logger.error("Failed to acquire OFFER after retries. Aborting.")
                return False
                
            # --- REQUESTING Stage (REQUEST -> ACK) ---
            if not self._perform_requesting(xid, offered_ip):
                logger.error("Failed to acquire ACK after retries. Aborting.")
                return False
                
            logger.info(f"Handshake complete. Assigned IP: {self.assigned_ip}, Lease: {self.lease_time}s")
            return True
            
        except Exception as e:
            logger.exception(f"Unexpected error during DHCP handshake: {e}")
            return False
        finally:
            if self.sock:
                self.sock.close()
                self.sock = None

    def _perform_selecting(self, xid: int) -> Optional[str]:
        """Runs the DISCOVER -> OFFER stage."""
        self._transition(self.SELECTING)
        timeout = self.INITIAL_TIMEOUT
        
        for attempt in range(1, self.MAX_RETRIES_PER_STAGE + 1):
            # Target IP logic (fallback)
            dest_ip = "255.255.255.255"
            if attempt > self.FALLBACK_THRESHOLD:
                dest_ip = self.SERVER_FALLBACK_IP
                logger.warning(f"Broadcast may be unreliable. Falling back to {dest_ip} for DISCOVER.")
            
            discover = DHCPPacket(message_type="DISCOVER", xid=xid, client_mac=self.mac_address)
            self._send_packet(discover, dest_ip)
            
            # Wait for matching OFFER
            start_time = time.time()
            while time.time() - start_time < timeout:
                remaining = max(0.1, timeout - (time.time() - start_time))
                packet = self._receive_packet(remaining)
                
                if packet and packet.xid == xid and packet.message_type == "OFFER":
                    if packet.offered_ip:
                        self.lease_time = packet.lease_time
                        logger.info(f"Received OFFER for {packet.offered_ip} (Lease: {packet.lease_time}s)")
                        return packet.offered_ip
                    else:
                        logger.warning("Received OFFER without IP address. Ignoring.")
                elif packet:
                    logger.debug(f"Ignoring irrelevant packet: {packet.message_type} (XID: {packet.xid})")
            
            # Timeout/Retry logic
            logger.warning(f"DISCOVER attempt {attempt} timed out (timeout={timeout:.2f}s).")
            timeout *= 2  # Exponential backoff
            
        return None

    def _perform_requesting(self, xid: int, offered_ip: str) -> bool:
        """Runs the REQUEST -> ACK stage."""
        self._transition(self.REQUESTING)
        timeout = self.INITIAL_TIMEOUT
        
        for attempt in range(1, self.MAX_RETRIES_PER_STAGE + 1):
            dest_ip = "255.255.255.255"
            if attempt > self.FALLBACK_THRESHOLD:
                dest_ip = self.SERVER_FALLBACK_IP
                logger.warning(f"Broadcast may be unreliable. Falling back to {dest_ip} for REQUEST.")
                
            request = DHCPPacket(
                message_type="REQUEST", 
                xid=xid, 
                client_mac=self.mac_address,
                offered_ip=offered_ip
            )
            self._send_packet(request, dest_ip)
            
            # Wait for matching ACK
            start_time = time.time()
            while time.time() - start_time < timeout:
                remaining = max(0.1, timeout - (time.time() - start_time))
                packet = self._receive_packet(remaining)
                
                if packet and packet.xid == xid:
                    if packet.message_type == "ACK":
                        if packet.offered_ip == offered_ip:
                            self.assigned_ip = packet.offered_ip
                            self.lease_time = packet.lease_time
                            self.lease_expiry = time.monotonic() + self.lease_time
                            self._transition(self.BOUND)
                            return True
                        else:
                            logger.error(f"ACK IP mismatch: expected {offered_ip}, got {packet.offered_ip}")
                    elif packet.message_type == "NACK":
                        logger.error("Received NACK from server. Handshake failed.")
                        return False
                elif packet:
                    logger.debug(f"Ignoring irrelevant packet: {packet.message_type} (XID: {packet.xid})")
                    
            logger.warning(f"REQUEST attempt {attempt} timed out (timeout={timeout:.2f}s).")
            timeout *= 2
            
        return False

    def _transition(self, new_state: str) -> None:
        """Log and perform state transition."""
        logger.info(f"Transition: {self.state} -> {new_state}")
        self.state = new_state

if __name__ == "__main__":
    # Smoke test
    client = DHCPClient(mac_address="AA:BB:CC:DD:EE:FF")
    success = client.acquire_lease()
    print(f"Acquisition success: {success}")
    if success:
        print(f"Assigned IP: {client.assigned_ip}")
        print(f"Lease Expiry (Monotonic): {client.lease_expiry}")
