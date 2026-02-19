"""
Upload Logic Helper (Orchestrator).
Contains pure logic for file validation, chunking, and session management.
Does NOT handle transport or execution.
"""
import logging
import os
import math
from typing import Generator, Tuple, Optional, Dict, Any

from common.constants import MAX_FILE_SIZE

logger = logging.getLogger("UploadClient")

class UploadClient:
    """
    Pure logic orchestrator for file uploads.
    """
    def __init__(self):
        pass

    def validate_file(self, local_path: str) -> Optional[str]:
        """
        Validates file existence and size.
        Returns error message if invalid, None if valid.
        """
        if not os.path.exists(local_path):
            return f"File not found: {local_path}"
        
        file_size = os.path.getsize(local_path)
        if file_size > MAX_FILE_SIZE:
            return f"File size {file_size} exceeds limit {MAX_FILE_SIZE}"
            
        return None

    def get_file_info(self, local_path: str) -> Tuple[str, int]:
        """Returns (filename, filesize)."""
        return os.path.basename(local_path), os.path.getsize(local_path)

    def get_chunks(self, local_path: str, chunk_size: int = 8192) -> Generator[Tuple[int, bytes], None, None]:
        """
        Yields (offset, chunk_data) for the file.
        """
        file_size = os.path.getsize(local_path)
        offset = 0
        
        try:
            with open(local_path, "rb") as f:
                while offset < file_size:
                    chunk_data = f.read(chunk_size)
                    if not chunk_data:
                        break
                    yield offset, chunk_data
                    offset += len(chunk_data)
        except OSError as e:
            logger.error(f"Error reading file {local_path}: {e}")
            raise
