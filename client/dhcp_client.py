"""
DHCP Client Module.
Handles IP acquisition from the DHCP server.
"""
from typing import Optional

class DHCPClient:
    """
    Client for the Custom DHCP protocol.
    """
    def __init__(self):
        # TODO: Initialize DHCP client state
        pass

    def discover(self) -> None:
        """
        Send DHCP DISCOVER packet.
        """
        # TODO: Implement DISCOVER
        raise NotImplementedError

    def request(self, offered_ip: str) -> bool:
        """
        Send DHCP REQUEST for the offered IP.
        """
        # TODO: Implement REQUEST
        raise NotImplementedError
