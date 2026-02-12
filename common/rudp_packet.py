"""
RUDP Packet Structure.
Defines the binary format for Reliable UDP packets.
"""
from dataclasses import dataclass

@dataclass
class RUDPPacket:
    """
    RUDP Packet Definition.
    """
    seq_num: int
    ack_num: int
    flags: int
    payload: bytes

    def pack(self) -> bytes:
        # TODO: Implement struct.pack
        raise NotImplementedError

    @classmethod
    def unpack(cls, data: bytes) -> 'RUDPPacket':
        # TODO: Implement struct.unpack
        raise NotImplementedError
