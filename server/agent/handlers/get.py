"""
GET Handler.
Retrieves file content from the sandbox.
Strictly adheres to size limits and Mixed Mode response format.
"""
import json
import logging
import os
from common.app_envelope import AppHeader
from common.constants import MAX_FILE_SIZE
from common.errors import ErrorCode
from server.agent.validations import PolicyGuard

logger = logging.getLogger(__name__)

# Day 4 Constraint: Inline response limit
MAX_INLINE_SIZE = 64 * 1024  # 64 KB

def handle_get(header: AppHeader, payload: bytes, policy_guard: PolicyGuard) -> dict:
    """
    Handle GET opcode.
    Returns a dict containing metadata and the raw binary content.
    The Dispatcher/ResponseBuilder will handle formatting this into Mixed Mode.
    
    Structure returned to Dispatcher:
    {
        "filename": ...,
        "size": ...,
        "BINARY_CONTENT": <bytes>
    }
    """
    try:
        # 1. Parse Payload (JSON only for GET request)
        if not payload:
             logger.warning("GET request missing payload")
             raise ValueError("Missing payload")
             
        try:
            request_data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            logger.warning("Invalid JSON payload for GET")
            raise ValueError("Invalid JSON payload")
            
        filename = request_data.get('filename')
        # Ensure filename is present and is a string
        if not filename or not isinstance(filename, str):
             logger.warning("Missing 'filename' in GET request")
             raise ValueError("Missing 'filename'")

        # 2. Validation
        # Sandbox path validation (Traverses ../ check)
        try:
            abs_path = policy_guard.validate_path(filename)
        except ValueError as e:
            logger.warning(f"Path validation failed: {e}")
             # Re-raise to let Dispatcher handle it (usually 403/400)
            raise

        # 3. File Existence
        if not os.path.exists(abs_path):
            logger.warning(f"File not found: {filename}")
            raise FileNotFoundError(f"File not found: {filename}")
            
        # 4. Size Checks
        file_size = os.path.getsize(abs_path)
        
        if file_size > MAX_FILE_SIZE:
             logger.warning(f"File too large: {file_size} > {MAX_FILE_SIZE}")
             raise ValueError(f"File too large: {file_size} > {MAX_FILE_SIZE}")

        # 5. Read File
        with open(abs_path, 'rb') as f:
            file_content = f.read()
            
        logger.info(f"GET: Successfully read {file_size} bytes from {filename}")
            
        # 6. Return Data
        return {
            "filename": filename,
            "size": file_size,
            "BINARY_CONTENT": file_content # Special key for Dispatcher extraction
        }

    except UnicodeDecodeError:
        logger.warning("Invalid payload encoding")
        raise ValueError("Invalid payload encoding")
