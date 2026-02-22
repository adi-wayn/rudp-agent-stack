import struct
from dataclasses import dataclass
from typing import Optional

# Formal RUDP Flags Vocabulary
FLAG_SYN = 0x01
FLAG_ACK = 0x02
FLAG_FIN = 0x04
FLAG_RST = 0x08

FIXED_HEADER_FORMAT = "!IIBHH"
FIXED_HEADER_SIZE = struct.calcsize(FIXED_HEADER_FORMAT)  # 13 bytes

REASSEMBLY_FORMAT = "!II"
REASSEMBLY_SIZE = struct.calcsize(REASSEMBLY_FORMAT)      # 8 bytes


class ChecksumError(ValueError):
    """Raised when an RUDP packet has an invalid checksum."""
    pass


@dataclass
class RUDPPacket:
    """
    RUDP Packet Definition.
    Structurally aligned with the System Specification (8.16).
    """
    # Fixed Header Fields (13 bytes)
    seq_num: int
    ack_num: int
    flags: int
    rwnd: int
    checksum: int = 0

    # Reassembly Fields (8 bytes, DATA packets only)
    msg_id: Optional[int] = None      # MUST equal request_id
    offset: Optional[int] = None      # Reassembly offset

    # Raw segment bytes
    payload: bytes = b""

    def calculate_checksum(self) -> int:
        """
        Calculates the 16-bit one's complement sum over the entire packet.
        The checksum field itself is treated as 0 during this calculation.
        According to RFC 768, if the calculated checksum is 0x0000, 
        it is transmitted as 0xFFFF.
        """
        # Pack header with checksum field set to 0
        header_bytes = struct.pack(
            FIXED_HEADER_FORMAT,
            self.seq_num,
            self.ack_num,
            self.flags,
            self.rwnd,
            0
        )
        
        packet_bytes = bytearray(header_bytes)
        
        # Add reassembly fields if present
        if self.msg_id is not None and self.offset is not None:
            reassembly_bytes = struct.pack(REASSEMBLY_FORMAT, self.msg_id, self.offset)
            packet_bytes.extend(reassembly_bytes)
            
        # Add payload
        if self.payload:
            packet_bytes.extend(self.payload)
            
        # Pad with zero byte if length is odd
        if len(packet_bytes) % 2 == 1:
            packet_bytes.append(0)
            
        # Calculate 16-bit one's complement sum
        csum = 0
        for i in range(0, len(packet_bytes), 2):
            word = (packet_bytes[i] << 8) + packet_bytes[i+1]
            csum += word
            
        # Add carry bits
        while (csum >> 16) > 0:
            csum = (csum & 0xFFFF) + (csum >> 16)
            
        # One's complement
        final_csum = ~csum & 0xFFFF
        
        # RFC 768 edge case: transmitted checksum of all zeros means no checksum.
        # So a calculated checksum of 0x0000 must be sent as 0xFFFF.
        return 0xFFFF if final_csum == 0x0000 else final_csum

    @property
    def is_syn(self) -> bool:
        """Returns True if the SYN flag is set."""
        return bool(self.flags & FLAG_SYN)

    @property
    def is_ack(self) -> bool:
        """Returns True if the ACK flag is set."""
        return bool(self.flags & FLAG_ACK)

    @property
    def is_fin(self) -> bool:
        """Returns True if the FIN flag is set."""
        return bool(self.flags & FLAG_FIN)

    @property
    def is_rst(self) -> bool:
        """Returns True if the RST flag is set."""
        return bool(self.flags & FLAG_RST)

    @property
    def has_data(self) -> bool:
        """Returns True if the packet contains payload OR reassembly fields."""
        return bool(self.payload) or (self.msg_id is not None and self.offset is not None)


    def pack(self) -> bytes:
        """
        Packs the RUDP packet into a binary string.
        Automatically calculates the checksum and constructs the packet payload.
        """
        self.checksum = self.calculate_checksum()
        
        header_bytes = struct.pack(
            FIXED_HEADER_FORMAT,
            self.seq_num,
            self.ack_num,
            self.flags,
            self.rwnd,
            self.checksum
        )
        
        packet_bytes = bytearray(header_bytes)
        
        # Conditionally append reassembly fields for DATA packets
        if self.msg_id is not None and self.offset is not None:
            reassembly_bytes = struct.pack(REASSEMBLY_FORMAT, self.msg_id, self.offset)
            packet_bytes.extend(reassembly_bytes)
            
        # Append remaining payload
        if self.payload:
            packet_bytes.extend(self.payload)
            
        return bytes(packet_bytes)

    @classmethod
    def unpack(cls, data: bytes) -> 'RUDPPacket':
        """
        Unpacks incoming binary data into an RUDPPacket.
        Immediately validates the minimum length and checksum.
        """
        if len(data) < FIXED_HEADER_SIZE:
            raise ValueError(f"Packet too short to contain fixed header: {len(data)} bytes")
            
        seq_num, ack_num, flags, rwnd, checksum = struct.unpack(
            FIXED_HEADER_FORMAT, data[:FIXED_HEADER_SIZE]
        )
        
        packet = cls(
            seq_num=seq_num,
            ack_num=ack_num,
            flags=flags,
            rwnd=rwnd,
            checksum=checksum
        )
        
        # Differentiate between DATA and ACK-only based on presence of additional bytes
        has_payload_fields = len(data) > FIXED_HEADER_SIZE
        if has_payload_fields:
            if len(data) < FIXED_HEADER_SIZE + REASSEMBLY_SIZE:
                 raise ValueError("Packet has extra data but not enough for reassembly fields")
                 
            msg_id, offset = struct.unpack(
                REASSEMBLY_FORMAT, data[FIXED_HEADER_SIZE:FIXED_HEADER_SIZE + REASSEMBLY_SIZE]
            )
            packet.msg_id = msg_id
            packet.offset = offset
            packet.payload = data[FIXED_HEADER_SIZE + REASSEMBLY_SIZE:]
            
        # Validate Checksum
        calculated_csum = packet.calculate_checksum()
        if packet.checksum != calculated_csum:
            raise ChecksumError(f"Invalid checksum: expected {calculated_csum}, got {packet.checksum}")
            
        return packet
        
    @classmethod
    def from_bytes(cls, data: bytes) -> 'RUDPPacket':
        """Alias for unpack."""
        return cls.unpack(data)
