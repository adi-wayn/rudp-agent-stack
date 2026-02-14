"""
Validation Logic for Agent Server.
Enforces sandbox constraints and payload limits.
"""
import os
import logging
from common.errors import ErrorCode
from common.constants import MAX_FILE_SIZE, MAX_PAYLOAD_LEN

logger = logging.getLogger(__name__)

class PolicyGuard:
    """
    Enforces security policies:
    1. Sandbox confinement (Root-directory only).
    2. Path traversal prevention.
    3. File size limits.
    """
    
    def __init__(self, sandbox_root: str):
        self.sandbox_root = os.path.abspath(sandbox_root)
        if not os.path.exists(self.sandbox_root):
            os.makedirs(self.sandbox_root, exist_ok=True)
            
    def validate_path(self, filename: str) -> str:
        """
        Validates that the filename is safe and within the sandbox.
        Returns the absolute path if valid, raises ValueError if not.
        """
        if not filename:
            raise ValueError("Filename cannot be empty")
            
        # secure_filename equivalent logic: prevent path traversal
        clean_name = os.path.basename(filename)
        if clean_name != filename:
             # If basename differs, it implies directory components were present
             # Strict policy: Flat directory only as per "Root-directory only"
             logger.warning(f"Path traversal attempt or subdirectory blocked: {filename}")
             raise ValueError("Subdirectories not allowed in sandbox")

        full_path = os.path.join(self.sandbox_root, clean_name)
        
        # Double check with commonpath to be absolutely sure
        if os.path.commonpath([self.sandbox_root, full_path]) != self.sandbox_root:
            logger.error(f"Security breach attempt: {filename}")
            raise ValueError("Path traversal detected")
            
        return full_path

    def validate_payload_size(self, size: int):
        """
        Enforces MAX_PAYLOAD_LEN.
        """
        if size > MAX_PAYLOAD_LEN:
             logger.warning(f"Payload size {size} exceeds limit {MAX_PAYLOAD_LEN}")
             raise ValueError(f"Payload too large: {size} > {MAX_PAYLOAD_LEN}")

    def list_sandbox(self) -> list[str]:
        """
        Safely lists files in the sandbox.
        """
        return os.listdir(self.sandbox_root)
