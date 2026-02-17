"""
APPEND Handler.
Opcode: 0x04
Request: Mixed Mode [Meta][Binary]
Response: JSON
"""
from typing import Any, Dict, Optional
from common.constants import OP_APPEND
from client.agent.dispatcher import (
    ClientHandler, ClientRequestSpec, 
    ENCODING_MIXED, OperationResult
)

class AppendHandler(ClientHandler):
    def build_request(self, filename: str, data: bytes) -> ClientRequestSpec:
        return ClientRequestSpec(
            opcode=OP_APPEND,
            meta={"filename": filename},
            binary=data,
            encoding_mode=ENCODING_MIXED
        )

    def parse_response(self, status_code: int, meta: Dict[str, Any], binary: Optional[bytes]) -> OperationResult:
        # APPEND response is JSON only, so binary should be None/Empty
        # But AgentClient parser handles 'unexpected' binary by just passing it.
        # We ignore binary here.
        if status_code == 200:
            return OperationResult(status=200, data=meta)
        else:
            error_msg = meta.get("error", "Unknown APPEND Error")
            return OperationResult(status=status_code, error=error_msg, data=meta)
