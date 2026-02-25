import unittest
import socket
import time
import threading
from unittest.mock import Mock, patch

from client.transport.rudp_client import RUDPClientTransport
from common.rudp_packet import RUDPPacket, FLAG_ACK

class TestRUDPClientTransport(unittest.TestCase):
    def setUp(self):
        # Patch socket to avoid actual network binding during tests
        self.patcher = patch('socket.socket')
        self.mock_socket_class = self.patcher.start()
        self.mock_socket = self.mock_socket_class.return_value
        
        self.transport = RUDPClientTransport("127.0.0.1", 8080)

    def tearDown(self):
        self.transport.close()
        self.patcher.stop()

    def test_app_send_queues_via_sender(self):
        """Verify client.send() queues data directly to RUDPSender."""
        # Mock the underlying send mechanism so we can inspect it
        self.transport.send_raw_packet = Mock()
        
        self.transport.send(b"test_data", 123)
        
        # The sender should have internally chunked and appended to send_buffer.
        # But wait! _try_send gets called and triggers `self.sender.send_callback`.
        # Because we didn't mock send_raw_packet BEFORE transport.__init__, sender holds 
        # the original method reference which internally calls self.socket.send (our mocked socket).
        self.mock_socket.send.assert_called()
        self.assertEqual(len(self.transport.sender.unacked_packets), 1)
        self.assertEqual(self.transport.sender.next_seq, 1)

    def test_demultiplexing_ack_packet(self):
        """Verify ACK-only packets are routed to the Sender."""
        self.transport.sender.on_ack_received = Mock()
        self.transport.receiver.process_segment = Mock()
        
        # Build an ACK packet
        ack_packet = RUDPPacket(seq_num=0, ack_num=5, flags=FLAG_ACK, rwnd=64)
        
        # Directly invoke the router
        self.transport.on_packet_received(ack_packet, time.time())
        
        # Assert routing
        self.transport.sender.on_ack_received.assert_called_once()
        self.transport.receiver.process_segment.assert_not_called()

    def test_demultiplexing_data_packet(self):
        """Verify DATA packets are routed to the Receiver and return ACKs."""
        self.transport.sender.on_ack_received = Mock()
        
        # Mock receiver to return known values
        self.transport.receiver.process_segment = Mock(return_value=(0, 64, FLAG_ACK))
        self.transport.send_raw_packet = Mock()
        
        # Build a DATA packet
        data_packet = RUDPPacket(seq_num=0, ack_num=0, flags=0, rwnd=0, payload=b"hello", msg_id=1, offset=0)
        
        # Directly invoke the router
        self.transport.on_packet_received(data_packet, time.time())
        
        # Assert routing
        self.transport.sender.on_ack_received.assert_not_called()
        self.transport.receiver.process_segment.assert_called_once_with(data_packet)
        self.transport.send_raw_packet.assert_called_once()  # Asserts the ACK was fired

    def test_app_message_handler_bridging(self):
        """Verify the receiver delivers reassembled bytes back to the app layer."""
        delivered_data = []
        def app_callback(data: bytes):
            delivered_data.append(data)
            
        self.transport.set_message_handler(app_callback)
        
        # Mock an in-order chunk arriving
        self.transport.receiver.expected_seq = 1
        data_packet = RUDPPacket(seq_num=1, ack_num=0, flags=0, rwnd=0, payload=b"world", msg_id=1, offset=0)
        
        self.transport.on_packet_received(data_packet, time.time())
        
        self.assertEqual(len(delivered_data), 1)
        self.assertEqual(delivered_data[0], b"world")

    @patch('time.time')
    def test_receive_loop_acts_as_tick_generator(self, mock_time):
        """Verify time ticks the sender RTO loop upon every receive exception."""
        mock_time.return_value = 1000.0
        
        # Mock sender RTO check
        self.transport.sender.check_timeouts = Mock()
        
        # Mock socket to raise timeout to simulate blocking break
        self.mock_socket.recv.side_effect = socket.timeout
        
        # Start and briefly run the loop
        self.transport._running = True
        self.transport._receive_thread = threading.Thread(target=self.transport._receive_loop)
        self.transport._receive_thread.start()
        
        time.sleep(0.1) # Yield a tiny bit to allow thread iterations
        self.transport.close()
        
        # Assert the RTO timer was continuously ticked by the background unblocking exception
        self.assertTrue(self.transport.sender.check_timeouts.call_count > 0)


if __name__ == "__main__":
    unittest.main()
