"""
Reliable UDP Sender Logic (Layer 4)
Strictly adheres to System Specification Section 8.16.3 / 8.16.5.
Operates as a state machine using external time ticks for timeouts.
"""
import collections
import logging
from typing import Callable, Dict, Any
from enum import Enum

from common.rudp_packet import RUDPPacket
from common.constants import MSS, INITIAL_RTO, MAX_RWND

logger = logging.getLogger(__name__)

class CCState(Enum):
    CC_SLOW_START = 1
    CC_AVOIDANCE = 2
    CC_FAST_RECOVERY = 3


class RUDPSender:
    """
    RUDP Sender implementing sequence tracking, fixed sliding window,
    packet fragmentation, and tick-based RTO timeouts.
    """
    def __init__(self, send_callback: Callable[[bytes], None], window_size: int = MAX_RWND):
        """
        Initializes the Reliable UDP Sender.
        
        Args:
            send_callback: Function to invoke to send raw bytes over the network.
            window_size: Maximum number of unacknowledged packets allowed in flight.
        """
        from common.constants import INITIAL_CWND, INITIAL_SSTHRESH
        self.send_callback = send_callback
        self.window_size = window_size
        self.rto = INITIAL_RTO
        
        self.base = 0
        self.next_seq = 0
        
        # Congestion Control State
        self.cc_state = CCState.CC_SLOW_START
        self.cwnd = float(INITIAL_CWND)
        self.ssthresh = float(INITIAL_SSTHRESH)
        self.dup_ack_count = 0
        self.last_ack_received = 0
        self.inflight_bytes = 0
        
        # Maps seq_num -> {"packet": RUDPPacket, "sent_time": float}
        self.unacked_packets: Dict[int, Dict[str, Any]] = {}
        
        # Packets waiting to enter the window
        self.send_buffer = collections.deque()

    def enqueue_data(self, data: bytes, msg_id: int, current_time: float) -> None:
        """
        Fragments data based on MSS, creates packets, and appends to the send buffer.
        Automatically attempts to push new packets if the window allows.
        
        Args:
            data: Raw application data to send.
            msg_id: Request ID/Message ID to attach to the data packets.
            current_time: The current timestamp in seconds.
        """
        from common.rudp_packet import FLAG_FIN
        import math

        # Ensure we create at least one packet even if data is empty 
        # (e.g., for GET requests without payload but with msg_id).
        chunks = [data[i:i + MSS] for i in range(0, max(len(data), 1), MSS)]
        offset = 0
        
        for i, chunk in enumerate(chunks):
            # The last chunk marks the end of the message payload
            packet_flags = FLAG_FIN if i == len(chunks) - 1 else 0
            
            packet = RUDPPacket(
                seq_num=self.next_seq,
                ack_num=0,
                flags=packet_flags,
                rwnd=0,
                msg_id=msg_id,
                offset=offset,
                payload=chunk
            )
            self.send_buffer.append(packet)
            self.next_seq += 1
            offset += len(chunk)
            
        self._try_send(current_time)

    def _try_send(self, current_time: float) -> None:
        """
        Pushes packets from the send_buffer into the network if the window allows.
        Pipelining bounded by congestion window (cwnd) in bytes.
        """
        while self.send_buffer:
            next_packet = self.send_buffer[0]
            next_len = len(next_packet.payload)
            if self.inflight_bytes + next_len > self.cwnd:
                break
                
            packet = self.send_buffer.popleft()
            
            # Store packet in unacked map with sent timestamp
            self.unacked_packets[packet.seq_num] = {
                "packet": packet,
                "sent_time": current_time
            }
            self.inflight_bytes += len(packet.payload)
            
            try:
                self.send_callback(packet.pack())
            except Exception as e:
                logger.error("Failed to send packet seq=%d: %s", packet.seq_num, e)

    def on_ack_received(self, ack_num: int, current_time: float) -> None:
        """
        Processes an incoming ACK number. 
        Uses Cumulative ACK logic to clear the inflight buffer.
        
        Args:
            ack_num: The acknowledged sequence number.
            current_time: The current timestamp in seconds.
        """
        if ack_num > self.base:
            # New ACK
            self.base = ack_num
            self.dup_ack_count = 0
            self.last_ack_received = ack_num
            
            # Remove acknowledged packets and update inflight_bytes
            keys_to_remove = [seq for seq in self.unacked_packets.keys() if seq < ack_num]
            for seq in keys_to_remove:
                packet = self.unacked_packets[seq]["packet"]
                self.inflight_bytes -= len(packet.payload)
                del self.unacked_packets[seq]
                
            # Congestion Control State Machine (Growth)
            if self.cc_state == CCState.CC_SLOW_START:
                self.cwnd += MSS
                if self.cwnd >= self.ssthresh:
                    self.cc_state = CCState.CC_AVOIDANCE
            elif self.cc_state == CCState.CC_AVOIDANCE:
                self.cwnd += (MSS * MSS) / self.cwnd
            elif self.cc_state == CCState.CC_FAST_RECOVERY:
                self.cwnd = float(self.ssthresh)
                self.cc_state = CCState.CC_AVOIDANCE
                
            # Window has opened up, try to send more queued packets
            self._try_send(current_time)
            
        elif ack_num == self.last_ack_received and ack_num == self.base:
            # Duplicate ACK
            self.dup_ack_count += 1
            if self.dup_ack_count == 3 and self.cc_state != CCState.CC_FAST_RECOVERY:
                # Enter Fast Recovery
                self.cc_state = CCState.CC_FAST_RECOVERY
                self.ssthresh = max(self.cwnd / 2.0, 2.0 * MSS)
                self.cwnd = self.ssthresh + 3.0 * MSS
                
                # Fast Retransmit
                if self.base in self.unacked_packets:
                    packet = self.unacked_packets[self.base]["packet"]
                    try:
                        self.send_callback(packet.pack())
                    except Exception as e:
                        logger.error("Failed fast retransmit seq=%d: %s", self.base, e)
                        
            elif self.dup_ack_count > 3 and self.cc_state == CCState.CC_FAST_RECOVERY:
                # Inflate window
                self.cwnd += MSS
                self._try_send(current_time)

    def check_timeouts(self, current_time: float) -> None:
        """
        Tick-based RTO check. Evaluates the oldest inflight packet for retransmission.
        Does NOT use threads or asyncio.
        
        Args:
            current_time: The current timestamp in seconds.
        """
        if not self.unacked_packets:
            return
            
        # The oldest unacknowledged packet is always at seq_num == base
        if self.base in self.unacked_packets:
            oldest_info = self.unacked_packets[self.base]
            
            # Check if time elapsed exceeds Retransmission Timeout Engine
            if current_time - oldest_info["sent_time"] >= self.rto:
                logger.debug("Timeout for seq=%d, retransmitting.", self.base)
                
                # Congestion Control State Machine (Timeout)
                self.ssthresh = max(self.cwnd / 2.0, 2.0 * MSS)
                self.cwnd = float(MSS)
                self.cc_state = CCState.CC_SLOW_START
                
                # Update sent time to reset the timer
                oldest_info["sent_time"] = current_time
                
                # Retransmit ONLY the oldest unacknowledged packet
                try:
                    self.send_callback(oldest_info["packet"].pack())
                except Exception as e:
                    logger.error("Failed to retransmit packet seq=%d: %s", self.base, e)
