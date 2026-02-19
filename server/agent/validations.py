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
            
        # secure_filename logic:
        # We allow subdirectories IF they are within sandbox.
        # But we must prevent traversal (..)
        # The commonpath check below handles the security.
        # The basename check prevented ANY subdirectories, which breaks artifacts/.
        
        # Normalize path to handle .. and .
        # But wait, os.path.join might resolve .. before commonpath check?
        # Yes, os.path.abspath(os.path.join(root, filename)) resolves ..
        # So commonpath check IS the security.
        
        # We can remove the strict basename check allow subdirs.
        pass


        full_path = os.path.abspath(os.path.join(self.sandbox_root, filename))
        
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
