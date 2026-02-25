import unittest
import math
from common.rudp_packet import RUDPPacket
from common.rudp_receiver import RUDPReceiver, FCState
from common.constants import MAX_RWND

class TestRUDPReceiverRWND(unittest.TestCase):
    def setUp(self):
        self.delivered_payloads = []
        def deliver_cb(data):
            self.delivered_payloads.append(data)
        self.receiver = RUDPReceiver(deliver_cb)

    def test_rwnd_advertisement_decreases(self):
        """Verify rwnd decreases as ooo_buffer grows."""
        # expected_seq starts at 1
        # Fill ooo_buffer with 10 segments (seq 2 to 11)
        for i in range(2, 12):
            packet = RUDPPacket(seq_num=i, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"data")
            ack, rwnd, flags = self.receiver.process_segment(packet)
            # ooo_buffer size is i-1
            self.assertEqual(rwnd, MAX_RWND - (i - 1))
        
        self.assertEqual(len(self.receiver.ooo_buffer), 10)
        self.assertEqual(self.receiver.fc_state, FCState.NORMAL)

    def test_fc_throttle_transition(self):
        """Verify fc_state transitions to THROTTLE at 52 segments (80% of 64)."""
        # MAX_RWND = 64. High watermark = 80% = 51.2 -> 52.
        high_threshold = math.ceil(0.80 * MAX_RWND)
        self.assertEqual(high_threshold, 52)
        
        # Fill ooo_buffer up to 51 segments (seq 2 to 52)
        for i in range(2, 53):
            packet = RUDPPacket(seq_num=i, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"data")
            self.receiver.process_segment(packet)
            self.assertEqual(self.receiver.fc_state, FCState.NORMAL)
            
        # 52nd segment (seq 53) should trigger THROTTLE
        packet = RUDPPacket(seq_num=53, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"data")
        ack, rwnd, flags = self.receiver.process_segment(packet)
        self.assertEqual(self.receiver.fc_state, FCState.THROTTLE)
        self.assertEqual(self.receiver.stats["fc_throttle"], 1)
        self.assertEqual(rwnd, MAX_RWND - 52) # 64 - 52 = 12
        self.assertNotEqual(rwnd, 0) # MUST NOT be forced to 0 at 80%

    def test_fc_normal_transition_hysteresis(self):
        """Verify fc_state returns to NORMAL only at 13 segments (20% of 64)."""
        # Enter THROTTLE first
        for i in range(2, 54):
            packet = RUDPPacket(seq_num=i, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"data")
            self.receiver.process_segment(packet)
        self.assertEqual(self.receiver.fc_state, FCState.THROTTLE)
        
        # Drain ooo_buffer down to 14 segments (manual drain to simulate delivery)
        # Note: In real life, delivering seq 1 would drain contiguous. 
        # Here we just pop from ooo_buffer to test the state machine.
        while len(self.receiver.ooo_buffer) > 14:
            seq = next(iter(self.receiver.ooo_buffer))
            self.receiver.ooo_buffer.pop(seq)
            
        # One more segment arrival while at 14 shouldn't reset NORMAL yet
        packet = RUDPPacket(seq_num=100, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"dup")
        self.receiver.process_segment(packet)
        self.assertEqual(self.receiver.fc_state, FCState.THROTTLE)
        
        # Drain to 13
        self.receiver.ooo_buffer.pop(next(iter(self.receiver.ooo_buffer)))
        self.assertEqual(len(self.receiver.ooo_buffer), 13)
        
        # Next arrival should trigger NORMAL
        packet = RUDPPacket(seq_num=101, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"dup")
        ack, rwnd, flags = self.receiver.process_segment(packet)
        self.assertEqual(self.receiver.fc_state, FCState.NORMAL)
        self.assertEqual(self.receiver.stats["fc_normal"], 1)

    def test_rwnd_zero(self):
        """Verify rwnd = 0 when buffer is completely full."""
        for i in range(2, 2 + MAX_RWND):
            packet = RUDPPacket(seq_num=i, ack_num=0, flags=0, rwnd=MAX_RWND, payload=b"data")
            ack, rwnd, flags = self.receiver.process_segment(packet)
            
        self.assertEqual(len(self.receiver.ooo_buffer), MAX_RWND)
        self.assertEqual(rwnd, 0)

if __name__ == '__main__':
    unittest.main()
