import unittest
from common.rudp_sender import RUDPSender, CCState
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
        """1. Data larger than MSS is properly fragmented, initial cwnd limits to 1."""
        payload = b"X" * (int(2.5 * MSS))
        msg_id = 42
        self.sender.enqueue_data(payload, msg_id, self.current_time)
        
        # Only 1 packet sent due to cwnd=1 MSS
        self.assertEqual(len(self.sent_bytes), 1)
        self.assertEqual(len(self.sender.unacked_packets), 1)
        
        # ACK seq 0
        self.sender.on_ack_received(1, self.current_time)
        # cwnd is now 2 MSS, it should send the next 2 packets (remaining)
        self.assertEqual(len(self.sent_bytes), 3)
        
        p0 = RUDPPacket.from_bytes(self.sent_bytes[0])
        p1 = RUDPPacket.from_bytes(self.sent_bytes[1])
        p2 = RUDPPacket.from_bytes(self.sent_bytes[2])
        
        self.assertEqual(p0.seq_num, 0)
        self.assertEqual(p1.seq_num, 1)
        self.assertEqual(p2.seq_num, 2)
        self.assertEqual(len(p2.payload), int(0.5 * MSS))

    def test_slow_start_growth(self):
        """2. Validates cwnd growth in Slow Start."""
        payload = b"Y" * (10 * MSS)
        self.sender.enqueue_data(payload, 99, self.current_time)
        
        # Init: cwnd = 1 MSS, 1 sent
        self.assertEqual(len(self.sent_bytes), 1)
        
        # ACK 1 (seq 0) -> cwnd = 2 MSS. sends seq 1, 2
        self.sender.on_ack_received(1, self.current_time)
        self.assertEqual(len(self.sent_bytes), 3)
        self.assertEqual(self.sender.cwnd, 2.0 * MSS)
        self.assertEqual(self.sender.cc_state, CCState.CC_SLOW_START)
        
        # ACK 2 (seq 1) -> cwnd = 3 MSS. sends seq 3, 4
        self.sender.on_ack_received(2, self.current_time)
        self.assertEqual(len(self.sent_bytes), 5)
        self.assertEqual(self.sender.cwnd, 3.0 * MSS)
        self.assertEqual(self.sender.cc_state, CCState.CC_SLOW_START)

    def test_fast_retransmit(self):
        """3. Simulates 3 dup ACKs triggering Fast Retransmit."""
        payload = b"Z" * (10 * MSS)
        self.sender.enqueue_data(payload, 100, self.current_time)
        
        # Advance cwnd to 5 MSS so we can have enough inflight packets
        # seq 0 sent initially
        self.sender.on_ack_received(1, self.current_time) # cwnd 2, sends seq 1, 2
        self.sender.on_ack_received(2, self.current_time) # cwnd 3, sends seq 3, 4
        self.sender.on_ack_received(3, self.current_time) # cwnd 4, sends seq 5, 6
        self.sender.on_ack_received(4, self.current_time) # cwnd 5, sends seq 7, 8
        self.assertEqual(len(self.sent_bytes), 9) # up to seq 8 sent
        
        self.sent_bytes.clear() # Reset sent list for visibility
        
        # Now seq 4 is lost. Receives 5, 6, 7 natively. 
        # Receiver sends ACK 4 (three times dup)
        self.sender.on_ack_received(4, self.current_time) # dup 1
        self.sender.on_ack_received(4, self.current_time) # dup 2
        self.assertEqual(self.sender.cc_state, CCState.CC_SLOW_START)
        self.assertEqual(len(self.sent_bytes), 0) # No resend yet
        
        self.sender.on_ack_received(4, self.current_time) # dup 3 -> Fast Retransmit!
        
        self.assertEqual(self.sender.cc_state, CCState.CC_FAST_RECOVERY)
        self.assertEqual(self.sender.dup_ack_count, 3)
        
        # Should have sent exactly seq 4
        self.assertTrue(len(self.sent_bytes) >= 1)
        p_retransmit = RUDPPacket.from_bytes(self.sent_bytes[0])
        self.assertEqual(p_retransmit.seq_num, 4)
        
        # Test Recovery deflation: If new ACK acknowledges recovery, deflates to ssthresh and sets Avoidance.
        self.sender.on_ack_received(8, self.current_time) # Cumulative ACK for recovered
        self.assertEqual(self.sender.cc_state, CCState.CC_AVOIDANCE)
        self.assertEqual(self.sender.cwnd, float(self.sender.ssthresh))

    def test_tick_based_timeout_retransmission(self):
        """4. check_timeouts correctly retransmits only the oldest packet and drops cwnd."""
        payload = b"A" * (3 * MSS)
        self.sender.enqueue_data(payload, 101, self.current_time)
        
        self.assertEqual(len(self.sent_bytes), 1)
        self.sent_bytes.clear() 
        
        # Advance time just before RTO
        self.current_time += INITIAL_RTO - 0.01
        self.sender.check_timeouts(self.current_time)
        self.assertEqual(len(self.sent_bytes), 0)
        
        # Advance time past RTO
        self.current_time += 0.02
        self.sender.check_timeouts(self.current_time)
        
        self.assertEqual(len(self.sent_bytes), 1)
        retransmitted_packet = RUDPPacket.from_bytes(self.sent_bytes[0])
        self.assertEqual(retransmitted_packet.seq_num, 0)
        
        self.assertEqual(self.sender.cwnd, 1.0 * MSS)
        self.assertEqual(self.sender.cc_state, CCState.CC_SLOW_START)

    def test_empty_payload(self):
        """Ensure an empty payload still enqueues at least 1 packet with no data."""
        self.sender.enqueue_data(b"", 50, self.current_time)
        self.assertEqual(len(self.sent_bytes), 1)
        
        packet = RUDPPacket.from_bytes(self.sent_bytes[0])
        self.assertEqual(packet.payload, b"")
        self.assertEqual(packet.msg_id, 50)
        self.assertEqual(packet.seq_num, 0)

    def test_dynamic_rto_calculation(self):
        """5. Validates Jacobson/Karels math and Karn's Backoff in Dynamic RTO."""
        from common.constants import ALPHA, BETA, MAX_RTO
        
        payload = b"R" * (1 * MSS)
        self.sender.enqueue_data(payload, 102, self.current_time)
        
        # Test 1: First RTT Sample is measured directly
        self.current_time += 0.200 # +200ms RTT
        self.sender.on_ack_received(1, self.current_time)
        
        self.assertAlmostEqual(self.sender.srtt, 0.200)
        self.assertAlmostEqual(self.sender.rttvar, 0.100)
        
        # RTO = srtt + 4 * rttvar = 0.200 + 0.400 = 0.600
        self.assertAlmostEqual(self.sender.rto, 0.600)
        
        # Enqueue new data
        payload = b"E" * (1 * MSS)
        self.sender.enqueue_data(payload, 103, self.current_time)
        
        # Test 2: Second RTT Sample (EWMA logic) - suppose network speeds up
        self.current_time += 0.100 # + 100ms RTT
        self.sender.on_ack_received(2, self.current_time)
        
        # Expected Math:
        # rttvar = (1-0.25)*0.100 + 0.25*abs(0.200 - 0.100) = 0.075 + 0.025 = 0.100
        # srtt = (1-0.125)*0.200 + 0.125*0.100 = 0.175 + 0.0125 = 0.1875
        self.assertAlmostEqual(self.sender.rttvar, 0.100)
        self.assertAlmostEqual(self.sender.srtt, 0.1875)
        
        # RTO = 0.1875 + 4 * 0.100 = 0.5875
        self.assertAlmostEqual(self.sender.rto, 0.5875)
        
        # Test 3: Karn's Backoff 
        payload = b"K" * (1 * MSS)
        self.sender.enqueue_data(payload, 104, self.current_time)
        
        # Force a timeout event precisely
        self.current_time += self.sender.rto + 0.01
        self.sender.check_timeouts(self.current_time)
        
        # RTO should now double
        self.assertAlmostEqual(self.sender.rto, 0.5875 * 2.0)
        
        # Verify the "is_retransmitted" flag triggered Karn's algorithm
        # Send an ACK for this specific packet and verify SRTT/RTTVAR DO NOT CHANGE
        self.current_time += 0.500
        self.sender.on_ack_received(3, self.current_time)
        
        self.assertAlmostEqual(self.sender.rttvar, 0.100) # Unchanged from previous!
        self.assertAlmostEqual(self.sender.srtt, 0.1875) # Unchanged from previous!
