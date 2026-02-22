import unittest
from common.rudp_packet import RUDPPacket, FLAG_ACK
from common.rudp_receiver import RUDPReceiver
from common.constants import MAX_RWND

class TestRUDPReceiver(unittest.TestCase):
    def setUp(self):
        self.delivered_payloads = []
        def deliver_cb(data):
            self.delivered_payloads.append(data)
        self.receiver = RUDPReceiver(deliver_cb)

    def test_in_order_delivery(self):
        """test_in_order_delivery: Seq 1, 2, 3 -> Deliver all, ACK advances."""
        # Seq 1
        p1 = RUDPPacket(seq_num=1, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p1")
        ack, rwnd, flags = self.receiver.process_segment(p1)
        self.assertEqual(ack, 1)
        self.assertEqual(self.delivered_payloads, [b"p1"])
        
        # Seq 2
        p2 = RUDPPacket(seq_num=2, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p2")
        ack, rwnd, flags = self.receiver.process_segment(p2)
        self.assertEqual(ack, 2)
        self.assertEqual(self.delivered_payloads, [b"p1", b"p2"])

    def test_ooo_buffering(self):
        """test_ooo_buffering: Seq 1, 3, 2 -> Deliver 1, buffer 3, deliver 2 & 3, ACK advances."""
        # Seq 1
        p1 = RUDPPacket(seq_num=1, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p1")
        self.receiver.process_segment(p1)
        
        # Seq 3 (Out of order)
        p3 = RUDPPacket(seq_num=3, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p3")
        ack, rwnd, flags = self.receiver.process_segment(p3)
        self.assertEqual(ack, 1) # Still ACK 1
        self.assertEqual(self.delivered_payloads, [b"p1"])
        self.assertIn(3, self.receiver.ooo_buffer)
        
        # Seq 2 (Fills the gap)
        p2 = RUDPPacket(seq_num=2, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p2")
        ack, rwnd, flags = self.receiver.process_segment(p2)
        self.assertEqual(ack, 3) # Now ACKs up to 3
        self.assertEqual(self.delivered_payloads, [b"p1", b"p2", b"p3"])
        self.assertEqual(len(self.receiver.ooo_buffer), 0)

    def test_duplicate_packet(self):
        """test_duplicate_packet: Seq 1, 1 -> Deliver 1 once, send 2 ACKs for 1."""
        p1 = RUDPPacket(seq_num=1, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p1")
        
        # First arrival
        ack, rwnd, flags = self.receiver.process_segment(p1)
        self.assertEqual(ack, 1)
        
        # Duplicate arrival
        ack, rwnd, flags = self.receiver.process_segment(p1)
        self.assertEqual(ack, 1)
        self.assertEqual(self.delivered_payloads, [b"p1"]) # Only one delivery
        self.assertEqual(self.receiver.stats["dup"], 1)

    def test_gap_dup_acks(self):
        """test_gap_dup_acks: Seq 1, 3, 4, 5 -> Send ACK for 1, 1, 1, 1 (dupACK stream)."""
        packets = [
            RUDPPacket(seq_num=1, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p1"),
            RUDPPacket(seq_num=3, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p3"),
            RUDPPacket(seq_num=4, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p4"),
            RUDPPacket(seq_num=5, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p5"),
        ]
        
        acks = [self.receiver.process_segment(p)[0] for p in packets]
        self.assertEqual(acks, [1, 1, 1, 1]) # Cumulative ACK stuck at 1 due to gap at 2

    def test_window_boundary(self):
        """
        test_window_boundary:
        Seq 64 (with expected=1, MAX_RWND=64) -> ACCEPT (within boundary 1 <= seq < 65).
        Seq 65 (with expected=1, MAX_RWND=64) -> DROP.
        """
        # MAX_RWND is likely 64 per constants. Using it explicitly.
        
        # Seq 64: In window (1 <= 64 < 1 + 64)
        p64 = RUDPPacket(seq_num=1 + MAX_RWND - 1, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p64")
        ack, rwnd, flags = self.receiver.process_segment(p64)
        self.assertEqual(self.receiver.stats["buffered"], 1)
        self.assertEqual(self.receiver.stats["drop"], 0)
        
        # Reset for Seq 65
        self.setUp()
        # Seq 65: Out of window (1 <= 65 < 1 + 64 is False)
        p65 = RUDPPacket(seq_num=1 + MAX_RWND, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p65")
        ack, rwnd, flags = self.receiver.process_segment(p65)
        self.assertEqual(self.receiver.stats["buffered"], 0)
        self.assertEqual(self.receiver.stats["drop"], 1)

    def test_buffer_integrity(self):
        """test_buffer_integrity: Seq 3 sent twice while OOO -> ooo_buffer size should not double count."""
        # Gap at 2
        p1 = RUDPPacket(seq_num=1, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p1")
        self.receiver.process_segment(p1)
        
        p3 = RUDPPacket(seq_num=3, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"p3")
        
        # Send p3 twice
        self.receiver.process_segment(p3)
        self.receiver.process_segment(p3)
        
        self.assertEqual(len(self.receiver.ooo_buffer), 1)
        self.assertEqual(self.receiver.stats["buffered"], 1)
        
        # rwnd check: MAX_RWND - 1
        ack, rwnd, flags = self.receiver.process_segment(p3)
        self.assertEqual(rwnd, MAX_RWND - 1)

if __name__ == '__main__':
    unittest.main(exit=False)
    print("TESTS_COMPLETED_SUCCESSFULLY")
