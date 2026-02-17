"""
PUT_META Handler.
Opcode: 0x01
Request: JSON
Response: JSON
"""
from typing import Any, Dict, Optional
from common.constants import OP_PUT_META
from client.agent.dispatcher import (
    ClientHandler, ClientRequestSpec, 
    ENCODING_JSON, OperationResult
)

class PutMetaHandler(ClientHandler):
    def build_request(self, filename: str, total_size: int, overwrite: bool = True) -> ClientRequestSpec:
        return ClientRequestSpec(
            opcode=OP_PUT_META,
            meta={
                "filename": filename,
                "total_size": total_size,
                "overwrite": overwrite
            },
            binary=None,
            encoding_mode=ENCODING_JSON
        )

    def parse_response(self, status_code: int, meta: Dict[str, Any], binary: Optional[bytes]) -> OperationResult:
        if status_code == 200:
            # Success: Expect {"upload_id": "..."} inside data or root
            data = meta.get("data", {})
            upload_id = data.get("upload_id")
            if not upload_id and "upload_id" in meta:
                upload_id = meta["upload_id"]
                
            return OperationResult(status=200, data={"upload_id": upload_id})
        else:
            error_msg = meta.get("error", "Unknown PUT_META Error")
            return OperationResult(status=status_code, error=error_msg, data=meta)
