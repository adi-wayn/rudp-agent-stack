"""
GET Handler.
Opcode: 0x03
Request: JSON
Response: Mixed Mode (Success) or JSON (Error)
"""
from typing import Any, Dict, Optional
from common.constants import OP_GET
from client.agent.dispatcher import (
    ClientHandler, ClientRequestSpec, 
    ENCODING_JSON, OperationResult
)

class GetHandler(ClientHandler):
    def build_request(self, filename: str) -> ClientRequestSpec:
        return ClientRequestSpec(
            opcode=OP_GET,
            meta={"filename": filename},
            binary=None,
            encoding_mode=ENCODING_JSON
        )

    def parse_response(self, status_code: int, meta: Dict[str, Any], binary: Optional[bytes]) -> OperationResult:
        if status_code == 200:
            # Success: meta might contain info, binary is the file
            return OperationResult(status=200, data=binary)
        else:
            # Error: meta contains error message
            error_msg = meta.get("error", "Unknown GET Error")
            return OperationResult(status=status_code, error=error_msg)
