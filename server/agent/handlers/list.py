"""
LIST Operation Handler.
Returns a directory listing of the sandbox root.
"""
import logging
import json
from common.app_envelope import encode_message
from common.constants import OP_LIST, PROTOCOL_VERSION
from common.errors import ErrorCode
from server.agent.validations import PolicyGuard

logger = logging.getLogger(__name__)

def handle_list(request_context, policy_guard: PolicyGuard) -> bytes:
    """
    Executes the LIST operation.
    
    Args:
        request_context: Decoded request header/payload (Duck-typed or dataclass).
        policy_guard: Validated PolicyGuard instance.
        
    Returns:
        Encoded response message (Header + Payload).
    """
    try:
        # 1. Execute Logic: List sandbox directory
        files = policy_guard.list_sandbox()
        
        # 2. Format Response: JSON list of filenames
        # Spec 8.13 does not explicitly define LIST payload format beyond "structured",
        # but JSON is implied by metadata fields description.
        payload = json.dumps(files).encode("utf-8")
        
        # 3. Construct Response
        # Flags = 0 (No specific flags for simple LIST response)
        return encode_message(
            opcode=OP_LIST,
            flags=0,
            request_id=request_context.request_id,
            payload=payload
        )
        
    except Exception as e:
        logger.error(f"LIST operation failed: {e}")
        # Return Error Response
        # For simple errors, we might return a formatted error payload or rely on the Dispatcher to catch/format.
        # But given the handler signature returns bytes, let's bubble exception to Dispatcher 
        # which acts as the error boundary.
        raise e
