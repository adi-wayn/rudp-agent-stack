import unittest
from unittest.mock import patch, MagicMock
import socket
import logging

from client.transport.rudp_client import RUDPClientTransport
from common.rudp_packet import RUDPPacket, ChecksumError, FLAG_SYN

class TestRUDPClientTransport(unittest.TestCase):
    
    def setUp(self):
        self.host = '127.0.0.1'
        self.port = 12345
        
        self.patcher = patch('client.transport.rudp_client.socket.socket')
        self.mock_socket_class = self.patcher.start()
        
        self.mock_socket = MagicMock()
        self.mock_socket_class.return_value = self.mock_socket
        
        self.client = RUDPClientTransport(self.host, self.port)

    def tearDown(self):
        self.patcher.stop()

    def test_initialization_and_connect(self):
        """Test 1: Socket initialized and connect() called correctly"""
        # Ensure the socket was created with UDP params
        self.mock_socket_class.assert_called_with(socket.AF_INET, socket.SOCK_DGRAM)
        # Ensure the OS-level connect() trick is applied
        self.mock_socket.connect.assert_called_once_with((self.host, self.port))

    def test_send_raw_packet(self):
        """Test 2: send_raw_packet serializes and sends bytes"""
        packet = RUDPPacket(seq_num=100, ack_num=0, flags=FLAG_SYN, rwnd=64)
        expected_bytes = packet.pack()
        
        self.client.send_raw_packet(packet)
        self.mock_socket.send.assert_called_once_with(expected_bytes)

    @patch.object(RUDPClientTransport, 'on_packet_received')
    def test_receive_loop_valid_packet(self, mock_on_packet_received):
        """Test 3: Receive loop correctly processes valid bytes and calls on_packet_received"""
        # Create a valid packet
        packet = RUDPPacket(seq_num=200, ack_num=100, flags=0, rwnd=64)
        valid_bytes = packet.pack()
        
        # Setup socket.recv to return valid_bytes
        def mock_recv(bufsize):
            self.client._running = False
            return valid_bytes

        self.mock_socket.recv.side_effect = mock_recv
        self.client._running = True
        
        self.client._receive_loop()
        
        # Verify the packet was routed to the stub successfully
        mock_on_packet_received.assert_called_once()
        received_packet = mock_on_packet_received.call_args[0][0]
        self.assertEqual(received_packet.seq_num, 200)

    @patch('client.transport.rudp_client.logger')
    @patch.object(RUDPClientTransport, 'on_packet_received')
    def test_receive_loop_checksum_error(self, mock_on_packet_received, mock_logger):
        """Test 4: Receive loop gracefully handles ChecksumError (packet dropped, no crash)"""
        # Create a valid packet
        packet = RUDPPacket(seq_num=300, ack_num=0, flags=0, rwnd=64)
        valid_bytes = bytearray(packet.pack())
        
        # Corrupt the bytes slightly to trigger ChecksumError
        valid_bytes[-1] ^= 0xFF
        corrupted_bytes = bytes(valid_bytes)
        
        # Setup socket.recv to return corrupted_bytes on first call, then valid_bytes, then break
        valid_packet2 = RUDPPacket(seq_num=301, ack_num=0, flags=0, rwnd=64)
        valid_bytes2 = valid_packet2.pack()
        
        recv_returns = [corrupted_bytes, valid_bytes2]
        
        def mock_recv(bufsize):
            if not recv_returns:
                self.client._running = False
                return b""
            return recv_returns.pop(0)
            
        self.mock_socket.recv.side_effect = mock_recv
        self.client._running = True
        
        self.client._receive_loop()
        
        # Ensure we dropped the corrupted packet but processed the valid one after
        mock_on_packet_received.assert_called_once()
        received_packet = mock_on_packet_received.call_args[0][0]
        self.assertEqual(received_packet.seq_num, 301)
        
        # Ensure the warning was logged
        mock_logger.warning.assert_called_with(unittest.mock.ANY)

    def test_lifecycle_management(self):
        """Test 5: start() spins up daemon, close() terminates safely"""
        self.assertFalse(self.client._running)
        
        self.client.start()
        self.assertTrue(self.client._running)
        self.assertIsNotNone(self.client._receive_thread)
        self.assertTrue(self.client._receive_thread.daemon)
        
        # Mock thread to verify join
        with patch.object(self.client._receive_thread, 'join') as mock_join:
            with patch.object(self.client._receive_thread, 'is_alive', return_value=True):
                self.client.close()
                self.assertFalse(self.client._running)
                self.mock_socket.shutdown.assert_called_once_with(socket.SHUT_RDWR)
                self.mock_socket.close.assert_called_once()
                mock_join.assert_called_once_with(timeout=1.0)

if __name__ == '__main__':
    unittest.main()
