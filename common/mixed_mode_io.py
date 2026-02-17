"""
Mixed Mode I/O Utilities.
Handles the serialization and deserialization of Mixed Mode payloads:
[meta_len (4B)] [JSON metadata bytes] [raw binary bytes]

This ensures deterministic parsing for PUT_CHUNK, APPEND, and GET responses.
"""
import struct
import json
from typing import Tuple, Dict, Any, Optional

# Fixed 4-byte length prefix for metadata
# Network Byte Order (Big Endian)
META_LEN_FORMAT = "!I"
META_LEN_SIZE = struct.calcsize(META_LEN_FORMAT)

class MixedModeEncoder:
    """
    Encodes data into Mixed Mode format.
    """
    @staticmethod
    def encode(metadata: Dict[str, Any], binary_data: Optional[bytes] = None) -> bytes:
        """
        Encode metadata and optional binary data into a single byte stream.
        Format: [meta_len (4B)] [JSON bytes] [Binary bytes]
        """
        meta_bytes = json.dumps(metadata).encode("utf-8")
        meta_len = len(meta_bytes)
        
        # 1. Header: Metadata Length
        header = struct.pack(META_LEN_FORMAT, meta_len)
        
        # 2. Construct Payload
        payload = header + meta_bytes
        
        if binary_data:
            payload += binary_data
            
        return payload

class MixedModeDecoder:
    """
    Decodes data from Mixed Mode format.
    """
    @staticmethod
    def decode(data: bytes) -> Tuple[Dict[str, Any], bytes]:
        """
        Decode a Mixed Mode byte stream.
        Returns: (metadata_dict, binary_bytes)
        Raises: ValueError if format is invalid.
        """
        if len(data) < META_LEN_SIZE:
            raise ValueError("Payload too short to contain metadata length prefix")
            
        # 1. Read Metadata Length
        try:
            meta_len = struct.unpack(META_LEN_FORMAT, data[:META_LEN_SIZE])[0]
        except struct.error:
             raise ValueError("Failed to decode metadata length prefix")

        # 2. Validate Lengths
        total_len = len(data)
        required_len = META_LEN_SIZE + meta_len
        
        if total_len < required_len:
            raise ValueError(f"Payload incomplete. Expected at least {required_len} bytes, got {total_len}")
            
        # 3. Extract JSON
        meta_bytes = data[META_LEN_SIZE : META_LEN_SIZE + meta_len]
        try:
            metadata = json.loads(meta_bytes.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON metadata: {e}")
            
        # 4. Extract Binary
        binary_data = data[META_LEN_SIZE + meta_len:]
        
        return metadata, binary_data
