import unittest
import socket
import time
from unittest.mock import Mock, patch

from server.transport.rudp_server import RUDPServerTransport
from common.rudp_packet import RUDPPacket, FLAG_ACK

class TestRUDPServerTransport(unittest.TestCase):
    def setUp(self):
        # Patch socket to avoid actual network binding during tests
        self.patcher = patch('socket.socket')
        self.mock_socket_class = self.patcher.start()
        self.mock_socket = self.mock_socket_class.return_value
        
        self.transport = RUDPServerTransport(port=8080)

    def tearDown(self):
        self.transport.close()
        self.patcher.stop()

    def test_multiplexed_routing(self):
        """Send ACKs from two different clients, ensure they route to isolated state machines."""
        addr1 = ("127.0.0.1", 1111)
        addr2 = ("127.0.0.1", 2222)
        
        self.transport.send_raw_packet = Mock()
        
        # We need to construct data packets to force the server to create the isolated connections
        dp1 = RUDPPacket(seq_num=0, ack_num=0, flags=0, rwnd=0, payload=b"client1", msg_id=1, offset=0)
        dp2 = RUDPPacket(seq_num=0, ack_num=0, flags=0, rwnd=0, payload=b"client2", msg_id=2, offset=0)
        
        # Route them in
        self.transport._handle_datagram(dp1.pack(), addr1, time.time())
        self.transport._handle_datagram(dp2.pack(), addr2, time.time())
        
        # Connections dict should have 2 unique clients
        self.assertEqual(len(self.transport.connections), 2)
        
        conn1 = self.transport.connections[addr1]
        conn2 = self.transport.connections[addr2]
        
        # Send targeted ACKs
        ack_for_1 = RUDPPacket(seq_num=0, ack_num=5, flags=FLAG_ACK, rwnd=64)
        ack_for_2 = RUDPPacket(seq_num=0, ack_num=10, flags=FLAG_ACK, rwnd=64)
        
        # Mock internal handlers to ensure isolation
        conn1.sender.on_ack_received = Mock()
        conn2.sender.on_ack_received = Mock()
        
        self.transport._handle_datagram(ack_for_1.pack(), addr1, time.time())
        self.transport._handle_datagram(ack_for_2.pack(), addr2, time.time())
        
        # Verify completely isolated execution
        conn1.sender.on_ack_received.assert_called_once_with(5, getattr(conn1.sender.on_ack_received, 'call_args')[0][1])
        conn2.sender.on_ack_received.assert_called_once_with(10, getattr(conn2.sender.on_ack_received, 'call_args')[0][1])

    def test_app_send_mux(self):
        """Verify the server routes send calls down to specific client sender queues."""
        addr_z = ("192.168.1.10", 5555)
        
        self.transport.send_raw_packet = Mock()
        self.transport.send(b"response", 99, addr_z)
        
        # The transport should have lazily instantiated the connection
        self.assertIn(addr_z, self.transport.connections)
        
        # And added data to that specific sender
        conn_z = self.transport.connections[addr_z]
        self.assertEqual(len(conn_z.sender.unacked_packets), 1)

    @patch('time.time')
    def test_tick_engine_broadcast(self, mock_time):
        """Verify that standard loops broadcast ticks evenly to all connections."""
        mock_time.return_value = 1000.0
        
        addr1 = ("127.0.0.1", 1111)
        addr2 = ("127.0.0.1", 2222)
        
        # Force setup the two clients
        self.transport.send(b"ping", 1, addr1)
        self.transport.send(b"ping", 2, addr2)
        
        conn1 = self.transport.connections[addr1]
        conn2 = self.transport.connections[addr2]
        
        conn1.sender.check_timeouts = Mock()
        conn2.sender.check_timeouts = Mock()
        
        self.transport._tick_connections(2000.0)
        
        # Ensure both received the exact same global timestamp tick
        conn1.sender.check_timeouts.assert_called_once_with(2000.0)
        conn2.sender.check_timeouts.assert_called_once_with(2000.0)

if __name__ == "__main__":
    unittest.main()
