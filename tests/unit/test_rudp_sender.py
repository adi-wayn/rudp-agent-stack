import unittest
from common.rudp_sender import RUDPSender
from common.rudp_packet import RUDPPacket
from common.constants import MSS, INITIAL_RTO

class TestRUDPSender(unittest.TestCase):
    def setUp(self):
        self.sent_bytes = []
        
        def mock_send(data):
            self.sent_bytes.append(data)
            
        self.sender = RUDPSender(send_callback=mock_send, window_size=10)
        self.current_time = 1000.0

    def test_fragmentation_mss_limits(self):
        """1. Data larger than MSS is properly fragmented."""
        payload = b"X" * (int(2.5 * MSS))
        msg_id = 42
        self.sender.enqueue_data(payload, msg_id, self.current_time)
        
        self.assertEqual(len(self.sent_bytes), 3)
        self.assertEqual(len(self.sender.unacked_packets), 3)
        self.assertEqual(self.sender.next_seq, 3)
        
        p0 = RUDPPacket.from_bytes(self.sent_bytes[0])
        p1 = RUDPPacket.from_bytes(self.sent_bytes[1])
        p2 = RUDPPacket.from_bytes(self.sent_bytes[2])
        
        self.assertEqual(p0.seq_num, 0)
        self.assertEqual(p0.offset, 0)
        self.assertEqual(len(p0.payload), MSS)
        self.assertEqual(p0.msg_id, msg_id)
        
        self.assertEqual(p1.seq_num, 1)
        self.assertEqual(p1.offset, MSS)
        self.assertEqual(len(p1.payload), MSS)
        self.assertEqual(p1.msg_id, msg_id)
        
        self.assertEqual(p2.seq_num, 2)
        self.assertEqual(p2.offset, 2 * MSS)
        self.assertEqual(len(p2.payload), int(0.5 * MSS))
        self.assertEqual(p2.msg_id, msg_id)

    def test_sliding_window_respects_limit(self):
        """2. The sliding window respects window_size."""
        payload = b"Y" * (15 * MSS)
        self.sender.enqueue_data(payload, 99, self.current_time)
        
        self.assertEqual(len(self.sent_bytes), 10, "Only up to window_size packets should be sent")
        self.assertEqual(len(self.sender.unacked_packets), 10)
        self.assertEqual(len(self.sender.send_buffer), 5, "Remaining packets stay in send_buffer")
        
    def test_cumulative_ack(self):
        """3. on_ack_received correctly applies Cumulative ACK logic."""
        payload = b"Z" * (5 * MSS)
        self.sender.enqueue_data(payload, 100, self.current_time)
        
        self.assertEqual(len(self.sent_bytes), 5)
        self.assertEqual(self.sender.base, 0)
        
        # Acknowledge up to packet 3 (meaning seqs 0, 1, 2 are received)
        self.current_time += 0.1
        self.sender.on_ack_received(3, self.current_time)
        
        self.assertEqual(self.sender.base, 3)
        self.assertEqual(len(self.sender.unacked_packets), 2)
        
        # Assert seqs 0, 1, 2 are removed; 3 and 4 remain
        self.assertNotIn(0, self.sender.unacked_packets)
        self.assertNotIn(1, self.sender.unacked_packets)
        self.assertNotIn(2, self.sender.unacked_packets)
        self.assertIn(3, self.sender.unacked_packets)
        self.assertIn(4, self.sender.unacked_packets)

    def test_tick_based_timeout_retransmission(self):
        """4. check_timeouts correctly retransmits only the oldest packet."""
        payload = b"A" * (3 * MSS)
        self.sender.enqueue_data(payload, 101, self.current_time)
        
        self.assertEqual(len(self.sent_bytes), 3)
        self.sent_bytes.clear()  # Clear initial sends
        
        # Advance time just before RTO
        self.current_time += INITIAL_RTO - 0.01
        self.sender.check_timeouts(self.current_time)
        self.assertEqual(len(self.sent_bytes), 0, "Should not retransmit yet")
        
        # Advance time past RTO
        self.current_time += 0.02
        self.sender.check_timeouts(self.current_time)
        
        self.assertEqual(len(self.sent_bytes), 1, "Should retransmit exactly 1 packet")
        
        retransmitted_packet = RUDPPacket.from_bytes(self.sent_bytes[0])
        self.assertEqual(retransmitted_packet.seq_num, 0, "Should retransmit the oldest packet (seq=0)")
        
        # Another tick should not immediately retransmit again since sent_time was updated
        self.sent_bytes.clear()
        self.current_time += 0.1
        self.sender.check_timeouts(self.current_time)
        self.assertEqual(len(self.sent_bytes), 0)

    def test_empty_payload(self):
        """Ensure an empty payload still enqueues at least 1 packet with no data."""
        self.sender.enqueue_data(b"", 50, self.current_time)
        self.assertEqual(len(self.sent_bytes), 1)
        
        packet = RUDPPacket.from_bytes(self.sent_bytes[0])
        self.assertEqual(packet.payload, b"")
        self.assertEqual(packet.msg_id, 50)
        self.assertEqual(packet.offset, 0)
        self.assertEqual(packet.seq_num, 0)

if __name__ == "__main__":
    unittest.main()
