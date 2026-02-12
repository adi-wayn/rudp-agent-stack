"""
Application Layer Envelope.
Defines the format for Agent messages.
"""
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class AppEnvelope:
    """
    Standard Application Message Envelope.
    """
    msg_type: str
    payload: Dict[str, Any]

    def to_bytes(self) -> bytes:
        # TODO: Serialize
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, data: bytes) -> 'AppEnvelope':
        # TODO: Deserialize
        raise NotImplementedError
