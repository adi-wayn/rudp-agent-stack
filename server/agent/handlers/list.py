"""
LIST Handler.
Lists files in the sandbox with metadata.
Returns deterministic sorted list.
"""
import logging
import os
from server.agent.validations import PolicyGuard

logger = logging.getLogger(__name__)

def handle_list(request_context, policy_guard: PolicyGuard) -> dict:
    """
    Executes the LIST operation.
    
    Args:
        request_context: Decoded request header/payload (Duck-typed or dataclass).
        policy_guard: Validated PolicyGuard instance.
        
    Returns:
        dict: { "files": [ { "name": str, "size": int, "mtime": float }, ... ] }
    """
    # 1. Execute Logic: List sandbox directory
    # policy_guard.list_sandbox() returns just names.
    # We need to iterate and get stats.
    
    # Ideally, PolicyGuard should just give us the safe root path?
    # Or we use list_sandbox and join?
    # PolicyGuard doesn't expose root path publicly usually?
    # Let's see if we can get the list of filenames and then stat them.
    # But `list_sandbox` returns relative paths?
    
    # If PolicyGuard.list_sandbox just returns names, we need to join with root.
    # Does PolicyGuard expose root? YES, `self.sandbox_root`.
    
    filenames = policy_guard.list_sandbox()
    
    # 2. Collect Metadata
    files_metadata = []
    for fname in filenames:
        # Construct absolute path safely?
        # PolicyGuard ensures `fname` is safe relative to root.
        # But `list_sandbox` might return just names in root.
        # We assume flat directory for now based on spec (sandbox root).
        
        abs_path = os.path.join(policy_guard.sandbox_root, fname)
        
        try:
            stats = os.stat(abs_path)
            files_metadata.append({
                "name": fname,
                "size": stats.st_size,
                "mtime": stats.st_mtime
            })
        except OSError:
            # Race condition: file deleted? Skip.
            continue
            
    # 3. Deterministic Sort
    files_metadata.sort(key=lambda x: x["name"])
    
    return {
        "files": files_metadata
    }
