"""
RUDP Receiver Logic.
Handles packet ordering and acknowledgments.
"""

import logging
from typing import Dict, List, Optional, Tuple, Callable
from common.rudp_packet import RUDPPacket, FLAG_ACK, ChecksumError
from common.constants import MAX_RWND

logger = logging.getLogger(__name__)

class RUDPReceiver:
    """
    RUDP Receiver Logic (Day 8).
    Handles out-of-order buffering, cumulative acknowledgments, 
    and duplicate ACK generation per peer.
    """
    def __init__(self, deliver_callback: Callable[[bytes], None]):
        """
        Initializes the receiver state.
        :param deliver_callback: Function to call with in-order payload bytes.
        """
        self.expected_seq = 1  # Next in-order sequence to deliver
        self.ooo_buffer: Dict[int, bytes] = {}  # seq -> payload
        self.deliver_callback = deliver_callback
        
        # Stats for observability
        self.stats = {
            "delivered": 0,
            "buffered": 0,
            "dup": 0,
            "drop": 0,
            "drop_invalid": 0
        }

    def process_segment(self, segment: RUDPPacket) -> Tuple[int, int, int]:
        """
        Processes an incoming RUDP segment and returns ACK parameters.
        :param segment: The unpacked RUDPPacket.
        :return: (ack_num, rwnd_advertised, flags)
        """
        seq = segment.seq_num
        action = "UNKNOWN"
        
        # 1. Checksum/Validity is already handled by RUDPPacket.unpack (raises ChecksumError)
        # However, the Plan says if it fails, drop but still ACK. 
        # RUDPClient/Server transport catches ChecksumError. 
        # If we reach here, it's valid. 
        # Note: If we wanted to handle ChecksumError here, we'd need bytes as input.
        # Following the plan's logic for valid segments:

        # 2. Window boundaries
        # expected_seq <= seq < expected_seq + MAX_RWND
        in_window = (self.expected_seq <= seq < self.expected_seq + MAX_RWND)
        is_duplicate = (seq < self.expected_seq)
        
        if is_duplicate:
            action = "DUP"
            self.stats["dup"] += 1
            # Do not deliver, just ACK current cumulative
        elif not in_window:
            action = "DROP"
            self.stats["drop"] += 1
            # Outside window, drop but still ACK current cumulative
        else:
            # 3. Handle In-order arrival
            if seq == self.expected_seq:
                action = "DELIVER"
                self.deliver_callback(segment.payload)
                self.expected_seq += 1
                self.stats["delivered"] += 1
                
                # Drain contiguous buffered segments
                drained_range_start = self.expected_seq
                while self.expected_seq in self.ooo_buffer:
                    payload = self.ooo_buffer.pop(self.expected_seq)
                    self.deliver_callback(payload)
                    self.expected_seq += 1
                    self.stats["delivered"] += 1
                
                if self.expected_seq > drained_range_start:
                    logger.debug(f"Drained OOO buffer: {drained_range_start}..{self.expected_seq-1}")
            
            # 4. Handle Out-of-order arrival (within window)
            else:
                action = "BUFFER"
                if seq not in self.ooo_buffer:
                    self.ooo_buffer[seq] = segment.payload
                    self.stats["buffered"] += 1
                # If already in buffer, we don't double count, just ACK again

        # 5. Cumulative ACK & rwnd Advertisement
        ack_num = self.expected_seq - 1
        rwnd = max(0, MAX_RWND - len(self.ooo_buffer))
        
        logger.debug(f"RECEIVER: seq={seq}, expected={self.expected_seq}, action={action}, "
                     f"ack_sent={ack_num}, rwnd_sent={rwnd}")
        
        return ack_num, rwnd, FLAG_ACK

