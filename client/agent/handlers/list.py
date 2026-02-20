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
            # Server wraps everything inside "data"
            payload = meta.get("data", {})

            # Now extract files safely
            if isinstance(payload, dict):
                files = payload.get("files", [])
            else:
                files = []

            return OperationResult(status=200, data=files)

        else:
            error_msg = meta.get("error", "Unknown LIST Error")
            return OperationResult(status=status_code, error=error_msg, data=meta)    