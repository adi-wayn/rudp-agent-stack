"""
Network Failure Simulation Engine.
Injects latency, packet loss, and reordering.
"""
import random
import threading
import logging
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)

class FailureEngine:
    """
    Intercepts and modifies network traffic for testing.
    """
    def __init__(self, drop_rate: float = 0.0, latency_ms: int = 0, dup_rate: float = 0.0):
        self.drop_rate = max(0.0, min(1.0, drop_rate))
        self.latency_ms = max(0, latency_ms)
        self.dup_rate = max(0.0, min(1.0, dup_rate))

    def should_drop_inbound(self) -> bool:
        """
        Returns True if the packet should be dropped based on drop_rate.
        """
        if self.drop_rate > 0 and random.random() < self.drop_rate:
            logger.debug(f"[FailureEngine] Dropped inbound packet (Rate: {self.drop_rate*100:.1f}%)")
            return True
        return False

    def apply_outbound(self, data: bytes, send_func: Callable, addr: Optional[Tuple[str, int]] = None):
        """
        Applies latency and duplication to outbound packets.
        """
        # 1. Duplication Injection (Happens immediately before potential latency)
        if self.dup_rate > 0 and random.random() < self.dup_rate:
            logger.debug(f"[FailureEngine] Duplicating outbound packet (Rate: {self.dup_rate*100:.1f}%)")
            # Fire an immediate duplicate
            if addr:
                send_func(data, addr)
            else:
                send_func(data)

        # 2. Latency Injection
        if self.latency_ms > 0:
            def delayed_send():
                if addr:
                    send_func(data, addr)
                else:
                    send_func(data)
            
            # Fire the actual packet after latency (non-blocking)
            timer = threading.Timer(self.latency_ms / 1000.0, delayed_send)
            timer.daemon = True # Ensure this doesn't hang the process on exit
            timer.start()
            logger.debug(f"[FailureEngine] Delayed outbound packet by {self.latency_ms}ms")
            
        else:
            # Normal send
            if addr:
                send_func(data, addr)
            else:
                send_func(data)
