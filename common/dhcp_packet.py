import json
from dataclasses import dataclass, asdict

@dataclass
class DHCPPacket:
    """
    DHCP Packet Definition
    Derived from System Specification Section 2 (DHCP Specification)
    """
    message_type: str  # "DISCOVER", "OFFER", "REQUEST", "ACK", "NACK"
    xid: int           # 32-bit transaction ID
    client_mac: str    # Client hardware identifier
    offered_ip: str = "" # 32-bit virtual pool address
    lease_time: int = 0  # 32-bit duration of allocation

    def to_bytes(self) -> bytes:
        """Serializes the DHCP packet to bytes using JSON."""
        return json.dumps(asdict(self)).encode('utf-8')

    @classmethod
    def from_bytes(cls, data: bytes) -> 'DHCPPacket':
        """Deserializes bytes into a DHCPPacket."""
        try:
            parsed = json.loads(data.decode('utf-8'))
            return cls(**parsed)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            raise ValueError(f"Invalid DHCP packet format: {e}")
