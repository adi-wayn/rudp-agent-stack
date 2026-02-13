"""
Agent Dispatcher.
Routes requests to appropriate handlers based on Opcode.
Handles error mapping and response construction via ResponseBuilder.
"""
import logging
from typing import Callable, Dict, Any

from common.constants import OP_LIST
from common.app_envelope import AppHeader
from common.errors import ErrorCode

from server.agent.validations import PolicyGuard
from server.agent.handlers.list import handle_list
from server.agent.response_builder import ResponseBuilder

logger = logging.getLogger(__name__)

class Dispatcher:
    """
    Orchestrates request routing and error handling.
    """
    def __init__(self, policy_guard: PolicyGuard):
        self.policy_guard = policy_guard
        # Map Opcode -> Handler Function
        # Handlers should return raw data (dict, list, etc.) or raise Exception
        self.handlers: Dict[int, Callable] = {
            OP_LIST: self._wrapper_list
        }

    def _wrapper_list(self, header: AppHeader, payload: bytes) -> Any:
        """
        Wrapper for LIST handler.
        """
        # LIST ignores payload
        return handle_list(header, self.policy_guard)

    def dispatch(self, header: AppHeader, payload: bytes) -> bytes:
        """
        Route request to handler and build response.
        Returns: Encoded App Envelope (Header + JSON Payload)
        """
        handler = self.handlers.get(header.opcode)
        
        if not handler:
            logger.warning(f"Unknown Opcode: {header.opcode}")
            return ResponseBuilder.build_error_response(
                opcode=header.opcode,
                request_id=header.request_id,
                error_code=ErrorCode.BAD_REQUEST,
                message=f"Unknown Opcode: {header.opcode}"
            )

        try:
            # Execute Handler
            result_data = handler(header, payload)
            
            # Build Success Response
            return ResponseBuilder.build_response(
                opcode=header.opcode,
                request_id=header.request_id,
                status_code=ErrorCode.OK,
                data=result_data
            )
            
        except ValueError as e:
            # Domain/Validation Errors (often 400 or 403)
            # We can try to map message content to specific codes if needed,
            # or default to BAD_REQUEST for generic ValueErrors.
            # If PolicyGuard raises ValueError for traversal, it's technically Forbidden or Bad Request.
            # Let's check exception message or type if we had specific exceptions.
            # For now, generic mapping:
            error_code = ErrorCode.BAD_REQUEST
            if "traversal" in str(e).lower() or "not allowed" in str(e).lower():
                error_code = ErrorCode.FORBIDDEN
                
            logger.warning(f"Request Failed (User Error): {e}")
            return ResponseBuilder.build_error_response(
                opcode=header.opcode,
                request_id=header.request_id,
                error_code=error_code,
                message=str(e)
            )
            
        except Exception as e:
            # Internal/Unexpected Errors
            logger.error(f"Request Failed (Internal): {e}", exc_info=True)
            return ResponseBuilder.build_error_response(
                opcode=header.opcode,
                request_id=header.request_id,
                error_code=ErrorCode.INTERNAL_SERVER_ERROR,
                message="Internal Server Error"
            )
