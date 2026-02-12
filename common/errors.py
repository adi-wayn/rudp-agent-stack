"""
Common Error Definitions.
Derived strictly from docs/specs/System_Specification.md Section 8.3.
"""
from enum import IntEnum

class ErrorCode(IntEnum):
    """
    Application Layer Error Codes.
    Section 8.3 Error Code Definitions.
    """
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    PAYLOAD_TOO_LARGE = 413
    INTERNAL_SERVER_ERROR = 500

class RUDPError(Exception):
    """Base class for RUDP transport errors."""
    pass

class TimeoutError(RUDPError):
    """Raised when an operation times out (e.g., MAX_RETRIES reached)."""
    pass

class ProtocolError(RUDPError):
    """Raised when a protocol violation occurs (e.g., invalid checksum, sequencing)."""
    pass
