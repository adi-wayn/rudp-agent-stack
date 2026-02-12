"""
Common Error Definitions.
"""

class RUDPError(Exception):
    """Base class for RUDP errors."""
    pass

class TimeoutError(RUDPError):
    """Raised when an operation times out."""
    pass
