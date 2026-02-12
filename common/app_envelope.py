"""
Application Layer Envelope.
Defines the format for Agent messages with a strict 12-byte binary header.
"""
import struct
from dataclasses import dataclass
from typing import Any, Dict, Optional
from .constants import PROTOCOL_VERSION, MAX_PAYLOAD_LEN

# Header Format:
# version (1B) | opcode (1B) | flags (1B) | reserved (1B)
# request_id (4B, unsigned)
# payload_len (4B, unsigned)
HEADER_FORMAT = "!BBBBII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

@dataclass
class AppHeader:
    """
    Decoded Application Header.
    """
    version: int
    opcode: int
    flags: int
    reserved: int
    request_id: int
    payload_len: int

def encode_header(version: int, opcode: int, flags: int, request_id: int, payload_len: int) -> bytes:
    """
    Encode the 12-byte application header.
    """
    if version != PROTOCOL_VERSION:
        raise ValueError(f"Invalid version: {version}. Expected {PROTOCOL_VERSION}")
    
    if payload_len > MAX_PAYLOAD_LEN:
        raise ValueError(f"Payload length {payload_len} exceeds max {MAX_PAYLOAD_LEN}")

    # Reserved field is always 0 on send
    return struct.pack(HEADER_FORMAT, version, opcode, flags, 0, request_id, payload_len)

def decode_header(data: bytes) -> AppHeader:
    """
    Decode the 12-byte application header.
    """
    if len(data) != HEADER_SIZE:
        raise ValueError(f"Invalid header size: {len(data)}. Expected {HEADER_SIZE}")

    version, opcode, flags, reserved, request_id, payload_len = struct.unpack(HEADER_FORMAT, data)

    if version != PROTOCOL_VERSION:
        raise ValueError(f"Invalid version: {version}. Expected {PROTOCOL_VERSION}")
    
    if payload_len > MAX_PAYLOAD_LEN:
        raise ValueError(f"Payload length {payload_len} exceeds max {MAX_PAYLOAD_LEN}")

    return AppHeader(version, opcode, flags, reserved, request_id, payload_len)

def encode_message(opcode: int, flags: int, request_id: int, payload: bytes) -> bytes:
    """
    Helper to encode a full message (Header + Payload).
    """
    header = encode_header(PROTOCOL_VERSION, opcode, flags, request_id, len(payload))
    return header + payload

# Note: Message decoding usually involves reading the header first, then the payload.
# This should be handled by the transport receiver loop (e.g. TCP stream reader).
