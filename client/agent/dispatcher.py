"""
Client Dispatcher Module.
Registry for Opcode -> Handler mappings and Protocol Definitions.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union, Protocol
from abc import ABC, abstractmethod

from common.constants import (
    OP_GET, OP_APPEND, OP_LIST, 
    OP_PUT_META, OP_PUT_CHUNK
)

# Encoding Modes
ENCODING_JSON = "JSON"
ENCODING_MIXED = "MIXED"

@dataclass
class ClientRequestSpec:
    """
    Specification for an outbound request.
    Produced by handlers, consumed by AgentClient.
    """
    opcode: int
    meta: Dict[str, Any] = field(default_factory=dict)
    binary: Optional[bytes] = None
    encoding_mode: str = ENCODING_JSON

@dataclass
class OperationResult:
    """
    Unified result object for client operations.
    """
    status: int
    data: Optional[Union[Dict[str, Any], bytes]] = None
    error: Optional[str] = None

class ClientHandler(ABC):
    """
    Abstract Base Class for Client-Side Opcode Handlers.
    Supports two modes:
    1. Request/Response: build_request() -> parse_response()
    2. Orchestrator: is_orchestrator=True -> run()
    """
    
    @property
    def is_orchestrator(self) -> bool:
        """Override to True for high-level operations (e.g. Upload)."""
        return False

    def run(self, client: Any, **kwargs) -> OperationResult:
        """
        Entry point for Orchestrator Handlers.
        Takes the full client instance to orchestrate multiple sub-ops.
        """
        raise NotImplementedError("Orchestrator handlers must implement run()")

    @abstractmethod
    def build_request(self, **kwargs) -> ClientRequestSpec:
        """
        Construct the request specification from arguments.
        """
        ...

    @abstractmethod
    def parse_response(self, status_code: int, meta: Dict[str, Any], binary: Optional[bytes]) -> OperationResult:
        """
        Parse the decoded response parts into a final result.
        """
        ...

class ClientDispatcher:
    """
    Stateless registry for Client Handlers.
    """
    def __init__(self):
        self._handlers: Dict[int, ClientHandler] = {}

    def register(self, opcode: int, handler: ClientHandler):
        """
        Register a handler for an opcode.
        """
        self._handlers[opcode] = handler

    def get_handler(self, opcode: int) -> ClientHandler:
        """
        Retrieve a handler. Raises ValueError if not found.
        """
        if opcode not in self._handlers:
            raise ValueError(f"No handler registered for opcode {opcode:#x}")
        return self._handlers[opcode]
