import socket
import logging
from datetime import datetime

from common.constants import DHCP_SERVER_PORT, DHCP_CLIENT_PORT, LOOPBACK_IP
from common.dhcp_packet import DHCPPacket
from server.dhcp.ip_manager import IPManager

logger = logging.getLogger("DHCPServer")

class DHCPServer:
    """
    Implements the Day 11 DHCP Server.
    Handles raw UDP packet parsing, IP allocation via IPManager, and DORA handshakes.
    """
    def __init__(self, host: str = LOOPBACK_IP, port: int = DHCP_SERVER_PORT, client_port: int = DHCP_CLIENT_PORT):
        self.host = host
        self.port = port
        self.client_port = client_port
        self.ip_manager = IPManager()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Allows reusing address if restarted quickly
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def start(self):
        """Bind socket and loop forever."""
        self.socket.bind((self.host, self.port))
        logger.info(f"DHCP Server listening on {self.host}:{self.port}")
        
        try:
            self.serve_forever()
        except KeyboardInterrupt:
            logger.info("DHCP Server shutting down...")
        finally:
            self.socket.close()

    def serve_forever(self):
        """Main listening loop."""
        while True:
            try:
                data, addr = self.socket.recvfrom(4096)
                self.handle_packet(data, addr)
            except Exception as e:
                logger.error(f"Error processing packet: {e}")

    def handle_packet(self, data: bytes, addr: tuple):
        """Deserializes bytes to DHCPPacket and routes the message."""
        try:
            packet = DHCPPacket.from_bytes(data)
        except ValueError as e:
            logger.warning(f"Failed to parse DHCP packet from {addr}: {e}")
            return
            
        if packet.message_type == "DISCOVER":
            self._handle_discover(packet)
        elif packet.message_type == "REQUEST":
            self._handle_request(packet)
        else:
            logger.warning(f"Received unhandled message type: {packet.message_type}")

    def _handle_discover(self, packet: DHCPPacket):
        offered_ip, lease_time = self.ip_manager.handle_discover(packet.client_mac, packet.xid)
        
        if not offered_ip:
            logger.warning(f"DHCP pool exhausted or refused for MAC {packet.client_mac}")
            return
            
        offer_packet = DHCPPacket(
            message_type="OFFER",
            xid=packet.xid,
            client_mac=packet.client_mac,
            offered_ip=offered_ip,
            lease_time=lease_time
        )
        
        logger.debug(f"Offering IP {offered_ip} to {packet.client_mac} for XID {packet.xid}")
        self._send_packet(offer_packet)

    def _handle_request(self, packet: DHCPPacket):
        success = self.ip_manager.handle_request(packet.client_mac, packet.xid, packet.offered_ip)
        
        if success:
            ack_packet = DHCPPacket(
                message_type="ACK",
                xid=packet.xid,
                client_mac=packet.client_mac,
                offered_ip=packet.offered_ip,
                lease_time=packet.lease_time
            )
            # Find the actual expiration string
            lease = self.ip_manager.leased_ips.get(packet.client_mac)
            expiry_float = lease["expires_at"] if lease else 0.0
            expiry_str = datetime.fromtimestamp(expiry_float).strftime('%Y-%m-%d %H:%M:%S')
            
            # Formatted exactly per spec: 
            # logger.info(f"DHCP: XID={xid}, Allocated IP={ip}, Lease Expiry={expiry}")
            logger.info(f"DHCP: XID={packet.xid}, Allocated IP={packet.offered_ip}, Lease Expiry={expiry_str}")
            
            self._send_packet(ack_packet)
        else:
            nack_packet = DHCPPacket(
                message_type="NACK",
                xid=packet.xid,
                client_mac=packet.client_mac,
                offered_ip="",
                lease_time=0
            )
            logger.info(f"DHCP: XID={packet.xid}, IP Collision/Validation Failed, sending NACK")
            self._send_packet(nack_packet)

    def _send_packet(self, packet: DHCPPacket):
        """Transmits DHCP replies to the specified client port on the Loopback segment."""
        target = (LOOPBACK_IP, self.client_port)
        try:
            self.socket.sendto(packet.to_bytes(), target)
        except Exception as e:
            logger.error(f"Failed to send {packet.message_type} to {target}: {e}")


