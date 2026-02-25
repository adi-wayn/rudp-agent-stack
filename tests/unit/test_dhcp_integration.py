import pytest
import threading
import time
import socket
from common.dhcp_packet import DHCPPacket
from server.dhcp_server import DHCPServer

def test_dhcp_server_integration():
    # Start server on high ports to avoid sudo requirement
    server = DHCPServer(port=6767, client_port=6868)
    
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    
    time.sleep(0.1)  # Allow socket to bind
    
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_sock.bind(("127.0.0.1", 6868))
    client_sock.settimeout(1.0)
    
    mac = "11:22:33:44:55:66"
    xid = 5555
    
    try:
        # 1. Send DISCOVER
        discover = DHCPPacket("DISCOVER", xid, mac)
        client_sock.sendto(discover.to_bytes(), ("127.0.0.1", 6767))
        
        # 2. Receive OFFER
        data, _ = client_sock.recvfrom(4096)
        offer = DHCPPacket.from_bytes(data)
        assert offer.message_type == "OFFER"
        assert offer.offered_ip == "127.0.0.2"
        
        # 3. Send REQUEST
        request = DHCPPacket("REQUEST", xid, mac, offer.offered_ip, offer.lease_time)
        client_sock.sendto(request.to_bytes(), ("127.0.0.1", 6767))
        
        # 4. Receive ACK
        data, _ = client_sock.recvfrom(4096)
        ack = DHCPPacket.from_bytes(data)
        assert ack.message_type == "ACK"
        assert ack.offered_ip == "127.0.0.2"
        
    finally:
        client_sock.close()
        # Clean up the server socket so subsequent tests (if any) don't clash
        server.socket.close()
