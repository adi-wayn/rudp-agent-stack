import unittest
from unittest.mock import MagicMock, patch, call
import socket
import json
import time
from client.dhcp_client import DHCPClient
from common.dhcp_packet import DHCPPacket

class TestDHCPClient(unittest.TestCase):
    def setUp(self):
        self.mac = "AA:BB:CC:DD:EE:FF"
        self.client = DHCPClient(self.mac)
        
    @patch('socket.socket')
    def test_successful_dora(self, mock_socket):
        # Mocking socket and its behavior
        mock_sock_inst = MagicMock()
        mock_socket.return_value = mock_sock_inst
        
        # Define server responses
        xid = 12345
        offer_packet = DHCPPacket(
            message_type="OFFER", 
            xid=xid, 
            client_mac=self.mac, 
            offered_ip="127.0.0.10", 
            lease_time=3600
        )
        ack_packet = DHCPPacket(
            message_type="ACK", 
            xid=xid, 
            client_mac=self.mac, 
            offered_ip="127.0.0.10", 
            lease_time=3600
        )
        
        # recvfrom returns (data, address)
        mock_sock_inst.recvfrom.side_effect = [
            (offer_packet.to_bytes(), ("127.0.0.1", 67)),
            (ack_packet.to_bytes(), ("127.0.0.1", 67))
        ]
        
        # Patch random to get a predictable XID
        with patch('random.getrandbits', return_value=xid):
            success = self.client.acquire_lease()
            
        self.assertTrue(success)
        self.assertEqual(self.client.assigned_ip, "127.0.0.10")
        self.assertEqual(self.client.state, "BOUND")
        self.assertEqual(self.client.lease_time, 3600)
        
    @patch('socket.socket')
    @patch('time.time')
    @patch('time.sleep', return_value=None) # Speed up tests
    def test_timeout_and_retry_selecting(self, mock_sleep, mock_time, mock_socket):
        mock_sock_inst = MagicMock()
        mock_socket.return_value = mock_sock_inst
        
        # Mock time to avoid hanging in while loop
        # Each call returns subsequent value
        mock_time.side_effect = [
            0.0, 10.0, # First DISCOVER attempt (timeout occurs)
            10.0, 20.0, # Second attempt
            20.0, 30.0, # Third attempt
            30.0, 40.0, # Fourth attempt
            40.0, 50.0, # Fifth attempt
            50.0, 60.0  # Final failure
        ]
        
        # recvfrom always times out
        mock_sock_inst.recvfrom.side_effect = socket.timeout
        
        success = self.client.acquire_lease()
        
        self.assertFalse(success)
        self.assertEqual(mock_sock_inst.sendto.call_count, 5) # Max retries
        
    @patch('socket.socket')
    def test_xid_filtering(self, mock_socket):
        mock_sock_inst = MagicMock()
        mock_socket.return_value = mock_sock_inst
        
        correct_xid = 11111
        wrong_xid = 99999
        
        # Packet with wrong XID followed by correct one
        wrong_packet = DHCPPacket(message_type="OFFER", xid=wrong_xid, client_mac=self.mac, offered_ip="127.0.0.11")
        right_packet = DHCPPacket(message_type="OFFER", xid=correct_xid, client_mac=self.mac, offered_ip="127.0.0.10", lease_time=3600)
        ack_packet = DHCPPacket(message_type="ACK", xid=correct_xid, client_mac=self.mac, offered_ip="127.0.0.10", lease_time=3600)

        mock_sock_inst.recvfrom.side_effect = [
            (wrong_packet.to_bytes(), ("127.0.0.1", 67)),
            (right_packet.to_bytes(), ("127.0.0.1", 67)),
            (ack_packet.to_bytes(), ("127.0.0.1", 67))
        ]
        
        with patch('random.getrandbits', return_value=correct_xid):
            success = self.client.acquire_lease()
            
        self.assertTrue(success)
        self.assertEqual(self.client.assigned_ip, "127.0.0.10")

    @patch('socket.socket')
    @patch('time.time')
    def test_broadcast_fallback(self, mock_time, mock_socket):
        mock_sock_inst = MagicMock()
        mock_socket.return_value = mock_sock_inst
        
        xid = 54321
        # First 2 attempts timeout (causing fallback)
        # Attempt 3 succeeds with fallback address
        mock_time.side_effect = [
            0.0, 1.0, # Attempt 1 DISCOVER
            1.0, 3.0, # Attempt 2 DISCOVER
            3.0, 3.1, # Attempt 3 (OFFER received)
            3.1, 3.2  # REQUEST -> ACK
        ]
        
        offer = DHCPPacket(message_type="OFFER", xid=xid, client_mac=self.mac, offered_ip="127.0.1.1", lease_time=100)
        ack = DHCPPacket(message_type="ACK", xid=xid, client_mac=self.mac, offered_ip="127.0.1.1", lease_time=100)
        
        mock_sock_inst.recvfrom.side_effect = [
            socket.timeout, # Attempt 1
            socket.timeout, # Attempt 2
            (offer.to_bytes(), ("127.0.0.1", 67)), # Attempt 3 (Fallback IP should be used here)
            (ack.to_bytes(), ("127.0.0.1", 67))
        ]
        
        with patch('random.getrandbits', return_value=xid):
            success = self.client.acquire_lease()
            
        self.assertTrue(success)
        
        # Verify call arguments
        send_calls = mock_sock_inst.sendto.call_args_list
        # Call 1 & 2: Broadcast
        self.assertEqual(send_calls[0][0][1], ("255.255.255.255", 67))
        self.assertEqual(send_calls[1][0][1], ("255.255.255.255", 67))
        # Call 3: Fallback 127.0.0.1
        self.assertEqual(send_calls[2][0][1], ("127.0.0.1", 67))

if __name__ == "__main__":
    unittest.main()
