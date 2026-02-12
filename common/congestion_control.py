"""
Congestion Control Algorithms.
Implements AIMD and Slow Start.
"""

class CongestionControl:
    """
    Congestion Control State Machine.
    """
    def __init__(self):
        self.cwd = 1
        self.ssthresh = 64

    def on_ack(self):
        # TODO: Increase window
        pass

    def on_loss(self):
        # TODO: Decrease window
        pass
