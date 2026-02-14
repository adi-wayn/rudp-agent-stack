"""
Upload Session Manager.
Handles multi-packet file uploads with configurable reordering strategies.
Derived strictly from docs/specs/System_Specification.md.
"""
import time
import uuid
import logging
from enum import Enum, auto
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, field

from common.errors import ErrorCode

logger = logging.getLogger(__name__)

class UploadMode(Enum):
    """
    Defines how out-of-order chunks are handled.
    User requested configurable reordering strategy.
    """
    STRICT = auto()      # Reject out-of-order (Day 3 requirement)
    BUFFERABLE = auto()  # Buffer out-of-order chunks (Future proofing)

@dataclass
class UploadSession:
    """
    Tracks state of a single file upload session.
    """
    upload_id: str
    filename: str
    total_size: int
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    next_expected_offset: int = 0
    
    # For BUFFERABLE mode:
    # Key: offset, Value: chunk_bytes
    buffered_chunks: Dict[int, bytes] = field(default_factory=dict)

    def is_expired(self, ttl: float) -> bool:
        """Check if session has exceeded TTL."""
        return (time.time() - self.last_activity) > ttl

class UploadSessionManager:
    """
    Manages active upload sessions.
    Enforces rules for chunk application based on mode.
    """
    def __init__(self, upload_mode: UploadMode = UploadMode.STRICT, session_ttl: float = 300.0):
        self.sessions: Dict[str, UploadSession] = {}
        self.upload_mode = upload_mode
        self.session_ttl = session_ttl

    def create_session(self, filename: str, total_size: int) -> str:
        """
        Create a new upload session.
        Returns: upload_id
        """
        upload_id = str(uuid.uuid4())
        session = UploadSession(
            upload_id=upload_id,
            filename=filename,
            total_size=total_size
        )
        self.sessions[upload_id] = session
        logger.info(f"Created upload session {upload_id} for {filename} ({total_size} bytes)")
        return upload_id

    def get_session(self, upload_id: str) -> Optional[UploadSession]:
        """Retrieve a session by ID."""
        session = self.sessions.get(upload_id)
        if session:
            session.last_activity = time.time()
        return session

    def apply_chunk(self, upload_id: str, offset: int, chunk_data: bytes, file_writer_func) -> Tuple[bool, str]:
        """
        Apply a chunk to the session using the provided file writer function.
        
        Args:
            upload_id: The session ID.
            offset: The byte offset of the chunk.
            chunk_data: The raw bytes.
            file_writer_func: Callable(filename, offset, data) -> None.
                              Must handle the actual file I/O safely.

        Returns:
            (is_complete, message)
            
        Raises:
            ValueError (mapped to ErrorCode in Dispatcher) if validation fails.
        """
        session = self.get_session(upload_id)
        if not session:
            raise ValueError(f"Session {upload_id} not found")

        chunk_len = len(chunk_data)
        
        # 1. Duplicate Check (Idempotency for offset)
        if offset < session.next_expected_offset:
            # If we've already processed this range, we must check if it's a true duplicate
            # or a conflict. For simplicity and per spec "duplicate offsets MUST NOT re-write",
            # we assume if it starts before expected, it might be a retransmission.
            
            # Use strict boundary check: if the chunk ends before or at next_expected, it's fully redundant.
            if offset + chunk_len <= session.next_expected_offset:
                logger.info(f"Ignoring duplicate chunk for {upload_id} at offset {offset}")
                # Return current completion status
                return (session.next_expected_offset == session.total_size), "Duplicate ignored"
            
            # If it overlaps but extends beyond, that's complex and usually implies error in sliding window
            # or sender logic. For strict RUDP/Day 3, we can reject as conflict or overlap.
            raise ValueError(f"Overlapping chunk at {offset} (expected {session.next_expected_offset})")

        # 2. Sequential Check
        if offset == session.next_expected_offset:
            # Valid sequential chunk
            self._write_chunk(session, offset, chunk_data, file_writer_func)
            
            # Check if we can apply buffered chunks (if any)
            if self.upload_mode == UploadMode.BUFFERABLE:
                self._process_buffer(session, file_writer_func)
                
        else:
            # 3. Out-of-Order Handling
            if self.upload_mode == UploadMode.STRICT:
                raise ValueError(f"Out-of-order chunk: Got {offset}, expected {session.next_expected_offset}")
            
            elif self.upload_mode == UploadMode.BUFFERABLE:
                logger.info(f"Buffering out-of-order chunk for {upload_id} at offset {offset}")
                session.buffered_chunks[offset] = chunk_data
            
        # 4. Check for Completion
        if session.next_expected_offset == session.total_size:
            logger.info(f"Upload complete for session {upload_id}")
            self._finalize_session(upload_id)
            return True, "Upload Complete"
            
        return False, "Chunk Applied"

    def _write_chunk(self, session: UploadSession, offset: int, data: bytes, file_writer_func):
        """Internal helper to write data and advance offset."""
        file_writer_func(session.filename, offset, data)
        session.next_expected_offset += len(data)

    def _process_buffer(self, session: UploadSession, file_writer_func):
        """Try to apply buffered chunks sequentially."""
        while session.next_expected_offset in session.buffered_chunks:
            next_chunk = session.buffered_chunks.pop(session.next_expected_offset)
            self._write_chunk(session, session.next_expected_offset, next_chunk, file_writer_func)

    def _finalize_session(self, upload_id: str):
        """Cleanup completed session."""
        if upload_id in self.sessions:
            del self.sessions[upload_id]

    def cleanup_expired_sessions(self):
        """Remove sessions that have exceeded TTL."""
        expired = [
            uid for uid, s in self.sessions.items() 
            if s.is_expired(self.session_ttl)
        ]
        for uid in expired:
            logger.info(f"Cleaning up expired session {uid}")
            del self.sessions[uid]
