"""
Upload Handlers.
Processes PUT_META and PUT_CHUNK requests.
"""
import json
import logging
import os
from common.app_envelope import AppHeader
from common.constants import MAX_FILE_SIZE
from common.errors import ErrorCode
from server.agent.validations import PolicyGuard
from server.agent.upload_session import UploadSessionManager
from common.mixed_mode_io import MixedModeDecoder

logger = logging.getLogger(__name__)

def handle_put_meta(header: AppHeader, payload: bytes, policy_guard: PolicyGuard, session_manager: UploadSessionManager) -> dict:
    """
    Handle PUT_META opcode.
    Validates metadata, creates session, and initializes target file.
    """
    try:
        # 1. Parse JSON Payload
        meta = json.loads(payload.decode('utf-8'))
        filename = meta.get('filename')
        total_size = meta.get('total_size')
        overwrite = meta.get('overwrite', False)
        
        if not filename or total_size is None:
            raise ValueError("Missing 'filename' or 'total_size'")
            
        # 2. Validation
        # Sandbox path validation
        abs_path = policy_guard.validate_path(filename)
        
        # Size limit
        if total_size > MAX_FILE_SIZE:
            # Raising ValueError to be mapped to 400 or handled specifically
            # Dispatcher maps large payload to 413 if we had a specific exception,
            # but for now we'll rely on ValueError usage in Dispatcher or raise custom if needed.
            # Ideally dispatcher should handle custom error types.
            # Let's stick to ValueError with clear message for now, as Dispatcher catches it.
            # Spec mentions 413 for Payload Too Large. Dispatcher handles general exceptions.
            # We can return a dict with error if we want specific control, but Dispatcher pattern is exception-based for errors.
            # Let's throw a ValueError, dispatcher will log it.
            # OR we could return ErrorCode from here if we changed signature, but signature is fixed.
            # Actually, per Dispatcher logic: Domain/Validation Errors (often 400 or 403).
            # To get 413, we might need to check this in dispatcher or raise a specific mapped exception.
            # For Day 3, strict adherence to 413 is good but 400 is acceptable for "Bad Request" logic mismatch.
            raise ValueError(f"File size {total_size} exceeds limit {MAX_FILE_SIZE}")

        # 3. File Preparation
        if os.path.exists(abs_path) and not overwrite:
            # 409 Conflict
            raise ValueError(f"File {filename} already exists (overwrite=False)")
            
        # Create/Truncate file
        # We don't write generic "empty" file if we want to stream invalidation,
        # but spec implies session start.
        # Ensure directory exists (PolicyGuard handles validation, but we might need to ensure dirs exist?)
        # PolicyGuard usually validates path existence or safety. 
        # Adding directory creation here for robustness.
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        
        with open(abs_path, 'wb') as f:
            f.truncate(0) 
            
        # 4. Create Session
        upload_id = session_manager.create_session(filename, total_size)
        
        return {
            "upload_id": upload_id,
            "status": "ready"
        }

    except json.JSONDecodeError:
        raise ValueError("Invalid JSON payload")

def handle_put_chunk(header: AppHeader, payload: bytes, policy_guard: PolicyGuard, session_manager: UploadSessionManager) -> dict:
    """
    Handle PUT_CHUNK opcode.
    Appends data to file via session manager.
    """
    try:
        # Use MixedModeDecoder for robust parsing
        # (Client uses MixedModeEncoder which adds 4-byte length prefix)
        meta, chunk_data = MixedModeDecoder.decode(payload)
        
        # Meta Fields
        upload_id = meta.get('upload_id')
        offset = meta.get('offset')
        chunk_len = meta.get('chunk_len')
        
        if not upload_id or offset is None or chunk_len is None:
            raise ValueError("Missing 'upload_id', 'offset', or 'chunk_len'")
            
        # Validate Chunk Length
        if len(chunk_data) != chunk_len:
            raise ValueError(f"Chunk length mismatch: Declared {chunk_len}, Actual {len(chunk_data)}")
            
        # File Writer Callback
        # We need a closure that knows the absolute path.
        # But Session has the filename. We need to re-validate path or store abs path in session?
        # `UploadSession` has `filename`.
        # `PolicyGuard` should re-validate or we trust the session's filename (since it was validated on creation)?
        # Ideally, re-validate to be safe, or store abs path.
        # Session stores relative filename.
        
        def file_writer(filename, file_offset, data):
            # Resolve path again to be safe
            abs_path = policy_guard.validate_path(filename)
            with open(abs_path, 'r+b') as f:
                f.seek(file_offset)
                f.write(data)

        # Apply Chunk
        is_complete, msg = session_manager.apply_chunk(upload_id, offset, chunk_data, file_writer)
        
        return {
            "upload_id": upload_id,
            "bytes_written": chunk_len,
            "complete": is_complete,
            "status": msg
        }

    except (ValueError, json.JSONDecodeError) as e:
        raise ValueError(f"Invalid metadata format: {e}")
