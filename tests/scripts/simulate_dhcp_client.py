import socket
import logging
from common.constants import DHCP_SERVER_PORT, DHCP_CLIENT_PORT, LOOPBACK_IP
from common.dhcp_packet import DHCPPacket

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] CLIENT: %(message)s')
logger = logging.getLogger("DHCPClientSim")

def main():
    mac = "AA:BB:CC:DD:EE:FF"
    xid = 888888

    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        client_sock.bind((LOOPBACK_IP, DHCP_CLIENT_PORT))
    except Exception as e:
        logger.error(f"Failed to bind to {DHCP_CLIENT_PORT}: {e}")
        return

    client_sock.settimeout(2.0)

    # Send DISCOVER
    discover_pkt = DHCPPacket("DISCOVER", xid, mac)
    client_sock.sendto(discover_pkt.to_bytes(), (LOOPBACK_IP, DHCP_SERVER_PORT))
    logger.info("Sent DISCOVER")

    try:
        data, _ = client_sock.recvfrom(4096)
        offer_pkt = DHCPPacket.from_bytes(data)
        logger.info(f"Received {offer_pkt.message_type}: IP={offer_pkt.offered_ip}")

        # Send REQUEST
        req_pkt = DHCPPacket("REQUEST", xid, mac, offer_pkt.offered_ip, offer_pkt.lease_time)
        client_sock.sendto(req_pkt.to_bytes(), (LOOPBACK_IP, DHCP_SERVER_PORT))
        logger.info("Sent REQUEST")

        # Await ACK
        data, _ = client_sock.recvfrom(4096)
        ack_pkt = DHCPPacket.from_bytes(data)
        logger.info(f"Received {ack_pkt.message_type}: IP={ack_pkt.offered_ip}")
        
    except socket.timeout:
        logger.error("Timed out waiting for server response.")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        client_sock.close()

if __name__ == "__main__":
    main()
