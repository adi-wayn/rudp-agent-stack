"""
LIST Handler.
Opcode: 0x05
Request: JSON {}
Response: JSON
"""
from typing import Any, Dict, Optional
from common.constants import OP_LIST
from client.agent.dispatcher import (
    ClientHandler, ClientRequestSpec, 
    ENCODING_JSON, OperationResult
)

class ListHandler(ClientHandler):
    def build_request(self) -> ClientRequestSpec:
        return ClientRequestSpec(
            opcode=OP_LIST,
            meta={},  # Empty JSON object
            binary=None,
            encoding_mode=ENCODING_JSON
        )

    def parse_response(self, status_code: int, meta: Dict[str, Any], binary: Optional[bytes]) -> OperationResult:
        if status_code == 200:
            # Protocol: {"files": [...]} or legacy {"data": [...]}
            files = meta.get("files", meta.get("data", []))
            return OperationResult(status=200, data=files)
        else:
            error_msg = meta.get("error", "Unknown LIST Error")
            return OperationResult(status=status_code, error=error_msg, data=meta)
