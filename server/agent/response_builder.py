"""
Response Builder.
Centralizes the construction of Application Layer responses.
Ensures consistent JSON payload structure for both success and error cases.
"""
import json
import logging
from typing import Any, Optional

from common.app_envelope import encode_message
from common.errors import ErrorCode

logger = logging.getLogger(__name__)

class ResponseBuilder:
    """
    Constructs spec-compliant responses.
    Spec 8.3: All responses SHALL include: request_id, status_code, optional message, optional payload.
    """
    
    @staticmethod
    def build_response(
        opcode: int,
        request_id: int,
        status_code: int,
        data: Optional[Any] = None,
        error_message: Optional[str] = None
    ) -> bytes:
        """
        Constructs the final response bytes (Header + JSON Payload).
        
        Payload Structure:
        {
            "status": <int>,       # Status Code (e.g. 200, 404)
            "error": <str|null>,   # Error message if failed
            "data": <any|null>     # Result data if success
        }
        """
        payload_dict = {
            "status": status_code,
            "error": error_message,
            "data": data
        }
        
        try:
            payload_bytes = json.dumps(payload_dict).encode("utf-8")
        except Exception as e:
            logger.error(f"Failed to serialize response payload: {e}")
            # Fallback to internal server error if serialization fails
            payload_bytes = json.dumps({
                "status": ErrorCode.INTERNAL_SERVER_ERROR,
                "error": "Response serialization failed",
                "data": None
            }).encode("utf-8")

        # Flags: 0 for now (or LAST_CHUNK if streaming involved, but Day 2 is atomic)
        return encode_message(
            opcode=opcode,
            flags=0, 
            request_id=request_id,
            payload=payload_bytes
        )

    @staticmethod
    def build_error_response(
        opcode: int,
        request_id: int,
        error_code: int,
        message: str
    ) -> bytes:
        """
        Helper for building error responses.
        """
        return ResponseBuilder.build_response(
            opcode=opcode,
            request_id=request_id,
            status_code=error_code,
            error_message=message
        )
