"""
Agent Dispatcher.
Routes requests to appropriate handlers based on Opcode.
Handles error mapping and response construction via ResponseBuilder.
"""
import logging
from typing import Callable, Dict, Any

from common.constants import (
    OP_LIST, OP_PUT_META, OP_PUT_CHUNK, OP_GET, OP_APPEND,
    OP_TASK_SEARCH_REPORT, OP_TASK_FILTER_LINES, OP_TASK_HASH_AND_STORE
)
from common.app_envelope import AppHeader
from common.errors import ErrorCode

from server.agent.validations import PolicyGuard
from server.agent.upload_session import UploadSessionManager
from server.agent.handlers.list import handle_list
from server.agent.handlers.put import handle_put_meta, handle_put_chunk
from server.agent.handlers.get import handle_get
from server.agent.handlers.append import handle_append
from server.agent.handlers.task import handle_task
from server.agent.tool_dispatcher import ToolDispatcher
from server.agent.idempotency import IdempotencyCache
from server.agent.response_builder import ResponseBuilder

logger = logging.getLogger(__name__)

class Dispatcher:
    """
    Orchestrates request routing and error handling.
    """
    def __init__(self, policy_guard: PolicyGuard, session_manager: UploadSessionManager, idempotency_cache: IdempotencyCache):
        self.policy_guard = policy_guard
        self.session_manager = session_manager
        self.idempotency_cache = idempotency_cache
        self.tool_dispatcher = ToolDispatcher(policy_guard)
        
        # Map Opcode -> Handler Function
        
        # Map Opcode -> Handler Function
        self.handlers: Dict[int, Callable] = {
            OP_LIST: self._wrapper_list,
            OP_PUT_META: self._wrapper_put_meta,
            OP_PUT_CHUNK: self._wrapper_put_chunk,
            OP_GET: self._wrapper_get,
            OP_GET: self._wrapper_get,
            OP_APPEND: self._wrapper_append,
            OP_TASK_SEARCH_REPORT: self._wrapper_task,
            OP_TASK_FILTER_LINES: self._wrapper_task,
            OP_TASK_HASH_AND_STORE: self._wrapper_task
        }

    def _wrapper_list(self, header: AppHeader, payload: bytes) -> Any:
        return handle_list(header, self.policy_guard)

    def _wrapper_put_meta(self, header: AppHeader, payload: bytes) -> Any:
        return handle_put_meta(header, payload, self.policy_guard, self.session_manager)

    def _wrapper_put_chunk(self, header: AppHeader, payload: bytes) -> Any:
        return handle_put_chunk(header, payload, self.policy_guard, self.session_manager)

    def _wrapper_get(self, header: AppHeader, payload: bytes) -> Any:
        # Ensure we pass header/payload
        return handle_get(header, payload, self.policy_guard)

    def _wrapper_append(self, header: AppHeader, payload: bytes) -> Any:
        # Pass idempotency cache (even if global check exists, specific logic might exist)
        # Note: The global check only prevents *re-execution* if fully cached.
        return handle_append(header, payload, self.policy_guard, self.idempotency_cache)

    def _wrapper_task(self, header: AppHeader, payload: bytes, client_address: tuple = None) -> Any:
        # Route to logic/agent/handlers/task.py
        # Pass tool_dispatcher instance
        return handle_task(header, payload, self.policy_guard, self.tool_dispatcher, self.idempotency_cache, client_address)

    def dispatch(self, header: AppHeader, payload: bytes, client_address: tuple = None) -> bytes:
        """
        Route request to handler and build response.
        Args:
            client_address: (ip, port) tuple from transport layer.
        Returns: Encoded App Envelope (Header + Payload)
        """
        logger.info(f"Dispatcher: Routing Opcode {hex(header.opcode)} for ReqID {header.request_id}")
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
            # Pass client_address to handler if it supports it
            # For now, we only updated handle_task. Other handlers might need it later.
            # We can inspect the handler signature or just pass it to all if we update all wrappers.
            # To avoid breaking existing wrappers, we'll update wrappers to accept **kwargs use it?
            # Or just update wrappers now.
            
            # Let's update `_wrapper_task` to pass it.
            if handler == self._wrapper_task:
                 result_data = handler(header, payload, client_address)
            else:
                 result_data = handler(header, payload)
            
            # If handler returns bytes, it has already built the response envelope
            if isinstance(result_data, bytes):
                return result_data
            
            # Extract Binary Content if present (Special Key from GET)
            binary_content = None
            if isinstance(result_data, dict) and "BINARY_CONTENT" in result_data:
                binary_content = result_data.pop("BINARY_CONTENT")
            
            # Build Success Response
            return ResponseBuilder.build_response(
                opcode=header.opcode,
                request_id=header.request_id,
                status_code=ErrorCode.OK,
                data=result_data,
                binary_data=binary_content
            )
            
        except FileNotFoundError as e:
            logger.warning(f"File Not Found: {e}")
            return ResponseBuilder.build_error_response(
                opcode=header.opcode,
                request_id=header.request_id,
                error_code=ErrorCode.NOT_FOUND,
                message=str(e)
            )

        except ValueError as e:
            # Domain/Validation Errors
            error_code = ErrorCode.BAD_REQUEST
            msg = str(e).lower()
            if "traversal" in msg or "not allowed" in msg:
                 error_code = ErrorCode.FORBIDDEN
            elif "too large" in msg or "exceeds" in msg:
                 error_code = ErrorCode.PAYLOAD_TOO_LARGE
                 
            logger.warning(f"Request Failed (User Error): {e}")
            return ResponseBuilder.build_error_response(
                opcode=header.opcode,
                request_id=header.request_id,
                error_code=error_code,
                message=str(e)
            )
            
        except Exception as e:
            logger.error(f"Request Failed (Internal): {e}", exc_info=True)
            return ResponseBuilder.build_error_response(
                opcode=header.opcode,
                request_id=header.request_id,
                error_code=ErrorCode.INTERNAL_SERVER_ERROR,
                message="Internal Server Error"
            )
