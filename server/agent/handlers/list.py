import logging
from server.agent.validations import PolicyGuard

logger = logging.getLogger(__name__)

def handle_list(request_context, policy_guard: PolicyGuard) -> list[str]:
    """
    Executes the LIST operation.
    
    Args:
        request_context: Decoded request header/payload (Duck-typed or dataclass).
        policy_guard: Validated PolicyGuard instance.
        
    Returns:
        List of filenames in the sandbox.
    """
    # 1. Execute Logic: List sandbox directory
    # Exceptions (ValueError, etc) will bubble up to Dispatcher
    return policy_guard.list_sandbox()
