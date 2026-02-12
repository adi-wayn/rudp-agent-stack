"""
Unit Tests for Application Envelope (Day 1).
"""
import pytest
import struct
from common.app_envelope import encode_header, decode_header, encode_message, HEADER_SIZE, AppHeader
from common.constants import PROTOCOL_VERSION, MAX_PAYLOAD_LEN

def test_app_envelope_roundtrip():
    """
    Verify that encoding and then decoding a header returns the same values.
    """
    opcode = 1
    flags = 0
    request_id = 12345
    payload_len = 100
    
    encoded = encode_header(PROTOCOL_VERSION, opcode, flags, request_id, payload_len)
    assert len(encoded) == HEADER_SIZE
    
    decoded = decode_header(encoded)
    assert decoded.version == PROTOCOL_VERSION
    assert decoded.opcode == opcode
    assert decoded.flags == flags
    assert decoded.reserved == 0
    assert decoded.request_id == request_id
    assert decoded.payload_len == payload_len

def test_app_envelope_invalid_payload_len():
    """
    Verify that payload length exceeding MAX_PAYLOAD_LEN raises ValueError.
    """
    with pytest.raises(ValueError, match="exceeds max"):
        encode_header(PROTOCOL_VERSION, 1, 0, 1, MAX_PAYLOAD_LEN + 1)
        
    # Also test decoding
    data = struct.pack("!BBBBII", PROTOCOL_VERSION, 1, 0, 0, 1, MAX_PAYLOAD_LEN + 1)
    with pytest.raises(ValueError, match="exceeds max"):
        decode_header(data)

def test_app_envelope_invalid_length():
    """
    Verify that providing bytes != 12 raises ValueError.
    """
    with pytest.raises(ValueError, match="Invalid header size"):
        decode_header(b'\x00' * 11)  # Too short
        
    with pytest.raises(ValueError, match="Invalid header size"):
        decode_header(b'\x00' * 13)  # Too long

def test_app_envelope_invalid_version():
    """
    Verify that incorrect protocol version raises ValueError.
    """
    with pytest.raises(ValueError, match="Invalid version"):
        encode_header(PROTOCOL_VERSION + 1, 1, 0, 1, 0)
        
    data = struct.pack("!BBBBII", PROTOCOL_VERSION + 1, 1, 0, 0, 1, 0)
    with pytest.raises(ValueError, match="Invalid version"):
        decode_header(data)

def test_encode_message_helper():
    """
    Verify the helper function encodes header + payload correctly.
    """
    payload = b"Hello World"
    encoded = encode_message(opcode=10, flags=2, request_id=99, payload=payload)
    
    assert len(encoded) == HEADER_SIZE + len(payload)
    
    header_bytes = encoded[:HEADER_SIZE]
    decoded_header = decode_header(header_bytes)
    
    assert decoded_header.payload_len == len(payload)
    assert encoded[HEADER_SIZE:] == payload
