import unittest
from common.rudp_sender import RUDPSender, CCState
from common.rudp_packet import RUDPPacket
from common.constants import MSS, MAX_RWND

class TestRUDPSenderRWND(unittest.TestCase):
    def setUp(self):
        self.sent_packets = []
        def mock_send(data):
            self.sent_packets.append(RUDPPacket.from_bytes(data))
        self.sender = RUDPSender(send_callback=mock_send, window_size=MAX_RWND)
        self.current_time = 1000.0

    def test_effective_window_enforcement_rwnd_limited(self):
        """Verify effective window is min(cwnd, rwnd) and limits sending."""
        # Initial cwnd = 1 MSS (1 segment). peer_rwnd = MAX_RWND (64 segments).
        # Effective window = 1 segment.
        
        payload = b"X" * (10 * MSS)
        self.sender.enqueue_data(payload, 42, self.current_time)
        
        self.assertEqual(len(self.sent_packets), 1)
        self.assertEqual(self.sender.effective_window, 1)
        
        # Advance cwnd to 4 MSS (4 segments)
        self.sender.on_ack_received(1, MAX_RWND, self.current_time) # cwnd 2
        self.sender.on_ack_received(2, MAX_RWND, self.current_time) # cwnd 3
        self.sender.on_ack_received(3, MAX_RWND, self.current_time) # cwnd 4
        
        # peer_rwnd is still 64. Effective window = 4.
        # Should have sent seq 0, 1, 2, 3, 4, 5, 6 (wait, let's trace:
        # seq 0 sent (cwnd 1)
        # ack 1 (seq 0) -> cwnd 2, sends 1, 2. total sent [0, 1, 2].
        # ack 2 (seq 1) -> cwnd 3, sends 3, 4. total sent [0, 1, 2, 3, 4].
        # ack 3 (seq 2) -> cwnd 4, sends 5, 6. total sent [0, 1, 2, 3, 4, 5, 6].
        self.assertEqual(len(self.sent_packets), 7)
        self.assertEqual(self.sender.effective_window, 4)
        
        # Now simulate receiver throttling: peer_rwnd = 2.
        # cwnd is still 4. Effective window = min(4, 2) = 2.
        # currently in-flight: base is 3 (seq 0,1,2 acked), next_seq is 7. 
        # in-flight segments = 7 - 3 = 4.
        # 4 >= 2, so should NOT send more.
        self.sent_packets.clear()
        self.sender.on_ack_received(4, 2, self.current_time) # cwnd increases, but peer_rwnd limits
        self.assertEqual(len(self.sent_packets), 0)
        self.assertEqual(self.sender.effective_window, 2)
        
        # ACK one more (base=4). in-flight = 7 - 4 = 3. 3 >= 2. still no send.
        self.sender.on_ack_received(5, 2, self.current_time)
        self.assertEqual(len(self.sent_packets), 0)

        # ACK one more (base=5). in-flight = 7 - 5 = 2. 2 >= 2. still no send.
        self.sender.on_ack_received(6, 2, self.current_time)
        self.assertEqual(len(self.sent_packets), 0)
        
        # ACK one more (base=6). in-flight = 7 - 6 = 1. 1 < 2. SHOULD send one!
        self.sender.on_ack_received(7, 2, self.current_time)
        self.assertEqual(len(self.sent_packets), 1)
        self.assertEqual(self.sent_packets[0].seq_num, 7)

    def test_rwnd_zero_pauses_sender(self):
        """Verify rwnd=0 completely pauses data transmission."""
        payload = b"Y" * (5 * MSS)
        self.sender.enqueue_data(payload, 43, self.current_time)
        
        # Initial: seq 0 sent.
        self.assertEqual(len(self.sent_packets), 1)
        
        # ACK 1 with rwnd=0
        self.sent_packets.clear()
        self.sender.on_ack_received(1, 0, self.current_time)
        
        self.assertEqual(self.sender.peer_rwnd, 0)
        self.assertEqual(self.sender.effective_window, 0)
        self.assertEqual(len(self.sent_packets), 0) # Should be paused
        
        # Even with high cwnd, rwnd=0 should block
        self.sender.cwnd = 100 * MSS
        self.sender.on_ack_received(1, 0, self.current_time)
        self.assertEqual(len(self.sent_packets), 0)

if __name__ == '__main__':
    unittest.main()
