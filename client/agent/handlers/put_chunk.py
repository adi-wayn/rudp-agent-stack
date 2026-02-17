"""
PUT_CHUNK Handler.
Opcode: 0x02
Request: Mixed Mode [Meta][Binary]
Response: JSON
"""
from typing import Any, Dict, Optional
from common.constants import OP_PUT_CHUNK
from client.agent.dispatcher import (
    ClientHandler, ClientRequestSpec, 
    ENCODING_MIXED, OperationResult
)

class PutChunkHandler(ClientHandler):
    def build_request(self, upload_id: str, offset: int, chunk_data: bytes) -> ClientRequestSpec:
        return ClientRequestSpec(
            opcode=OP_PUT_CHUNK,
            meta={
                "upload_id": upload_id,
                "offset": offset,
                "chunk_len": len(chunk_data)
            },
            binary=chunk_data,
            encoding_mode=ENCODING_MIXED
        )

    def parse_response(self, status_code: int, meta: Dict[str, Any], binary: Optional[bytes]) -> OperationResult:
        if status_code == 200:
            return OperationResult(status=200, data=meta)
        else:
            error_msg = meta.get("error", "Unknown PUT_CHUNK Error")
            return OperationResult(status=status_code, error=error_msg, data=meta)
