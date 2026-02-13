"""
Agent Dispatcher.
Routes requests to appropriate handlers based on Opcode.
"""
import logging
import struct
import json
from typing import Callable, Dict

from common.constants import (
    OP_LIST, 
    PROTOCOL_VERSION
)
from common.app_envelope import AppHeader, encode_message
from common.errors import ErrorCode

from server.agent.validations import PolicyGuard
from server.agent.handlers.list import handle_list

logger = logging.getLogger(__name__)

class Dispatcher:
    """
    Orchestrates request routing and error handling.
    """
    def __init__(self, policy_guard: PolicyGuard):
        self.policy_guard = policy_guard
        self.handlers: Dict[int, Callable] = {
            OP_LIST: self._wrapper_list
        }

    def _wrapper_list(self, header: AppHeader, payload: bytes) -> bytes:
        """
        Wrapper to match handler signature.
        """
        # LIST typically doesn't use payload, but we pass context if needed.
        return handle_list(header, self.policy_guard)

    def dispatch(self, header: AppHeader, payload: bytes) -> bytes:
        """
        Route request to handler.
        """
        handler = self.handlers.get(header.opcode)
        
        if not handler:
            logger.warning(f"Unknown Opcode: {header.opcode}")
            return self._create_error_response(
                header.request_id, 
                ErrorCode.BAD_REQUEST, 
                f"Unknown Opcode: {header.opcode}"
            )

        try:
            return handler(header, payload)
        except Exception as e:
            logger.error(f"Handler Loop Error: {e}", exc_info=True)
            return self._create_error_response(
                header.request_id, 
                ErrorCode.INTERNAL_SERVER_ERROR, 
                str(e)
            )

    def _create_error_response(self, request_id: int, code: int, message: str) -> bytes:
        """
        Generates a standardized error response.
        """
        # Error Payload: {"error": code, "message": "..."}
        error_payload = json.dumps({
            "status": code,
            "error": message
        }).encode("utf-8")
        
        # We REUSE the original Opcode? Or use a generic ERROR opcode?
        # The Spec doesn't define a specific ERROR opcode, but implies error codes in status.
        # Generally, we return the SAME opcode with an error payload or a specific flag?
        # Re-reading spec 8.3: "All responses SHALL include status_code".
        # 
        # Wait, the spec headers do NOT have a status_code field in the fixed 12-byte header.
        # "All responses SHALL include: request_id, status_code..."
        # This implies the status_code is part of the PAYLOAD or we need to overload a field.
        # 
        # Re-reading 8.1 Application Layer Message Envelope:
        # Header: Version, Opcode, Flags, Reserved, RequestID, PayloadLen.
        # 
        # If the header doesn't have status code, then the response payload MUST contain it.
        # "Unless otherwise specified, metadata fields SHALL be encoded as UTF-8 JSON immediately..."
        # 
        # Strategy:
        # For success (LIST), we returned just the list. We should wrap it? 
        # The Spec 8.3 says "All responses SHALL include... status_code".
        # 
        # Correct Approach:
        # The payload should be a JSON containing status_code and data?
        # OR the "Flags" field indicates error?
        # 
        # Let's verify standard response format.
        # Spec 8.3: "All responses SHALL include: request_id, status_code, optional message, optional payload"
        # 
        # This strongly suggests the Payload is a JSON envelope itself:
        # {
        #   "status": 200,
        #   "data": [...],
        #   ...
        # }
        
        return encode_message(
            opcode=0xFF, # Using 0xFF to indicate System/Error if original opcode unavailable or just reply with 0xFF? 
                         # Actually, cleaner to reply with original Opcode but valid error payload.
                         # BUT if opcode was unknown, what do we send back?
                         # Let's use 0x00 (No-Op) or just 0xFF (Error) or mirror the request opcode?
                         # Since we don't know the opcode, let's use 0xFF generic.
            flags=0,
            request_id=request_id,
            payload=error_payload
        )
