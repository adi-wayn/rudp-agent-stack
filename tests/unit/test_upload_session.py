"""
Unit tests for UploadSessionManager.
"""
import pytest
import time
from unittest.mock import MagicMock
from server.agent.upload_session import UploadSessionManager, UploadMode

@pytest.fixture
def session_manager():
    return UploadSessionManager(upload_mode=UploadMode.STRICT, session_ttl=1.0)

def test_create_session(session_manager):
    """Verify session creation."""
    uid = session_manager.create_session("test.txt", 100)
    assert uid
    session = session_manager.get_session(uid)
    assert session
    assert session.filename == "test.txt"
    assert session.total_size == 100
    assert session.next_expected_offset == 0

def test_apply_chunk_sequential(session_manager):
    """Verify sequential chunk application."""
    uid = session_manager.create_session("test.txt", 10)
    mock_writer = MagicMock()
    
    # Chunk 1: 0-5
    complete, msg = session_manager.apply_chunk(uid, 0, b'12345', mock_writer)
    assert not complete
    mock_writer.assert_called_with("test.txt", 0, b'12345')
    
    # Chunk 2: 5-10
    complete, msg = session_manager.apply_chunk(uid, 5, b'67890', mock_writer)
    assert complete
    mock_writer.assert_called_with("test.txt", 5, b'67890')
    
    # Session should be finalized/removed
    assert session_manager.get_session(uid) is None

def test_apply_chunk_duplicate_strict(session_manager):
    """Verify duplicate chunks are ignored in strict mode."""
    uid = session_manager.create_session("test.txt", 10)
    mock_writer = MagicMock()
    
    # Chunk 1: 0-5
    session_manager.apply_chunk(uid, 0, b'12345', mock_writer)
    
    # Resend Chunk 1
    complete, msg = session_manager.apply_chunk(uid, 0, b'12345', mock_writer)
    assert not complete
    assert "Duplicate" in msg
    # Writer should NOT be called again
    assert mock_writer.call_count == 1

def test_apply_chunk_out_of_order_strict(session_manager):
    """Verify out-of-order chunks raise error in strict mode."""
    uid = session_manager.create_session("test.txt", 10)
    mock_writer = MagicMock()
    
    # Chunk 2 first: 5-10 (Expected 0)
    with pytest.raises(ValueError, match="Out-of-order"):
        session_manager.apply_chunk(uid, 5, b'67890', mock_writer)

def test_apply_chunk_bufferable():
    """Verify buffering behavior."""
    manager = UploadSessionManager(upload_mode=UploadMode.BUFFERABLE)
    uid = manager.create_session("test.txt", 15)
    mock_writer = MagicMock()
    
    # Send Chunk 3: 10-15 (Buffered)
    manager.apply_chunk(uid, 10, b'ABCDE', mock_writer)
    assert mock_writer.call_count == 0
    session = manager.get_session(uid)
    assert 10 in session.buffered_chunks
    
    # Send Chunk 1: 0-5 (Applied)
    manager.apply_chunk(uid, 0, b'12345', mock_writer)
    assert mock_writer.call_count == 1
    
    # Send Chunk 2: 5-10 (Applied + Trigger Buffered Chunk 3)
    complete, msg = manager.apply_chunk(uid, 5, b'67890', mock_writer)
    
    assert complete
    assert mock_writer.call_count == 3
    # Verify order of calls
    mock_writer.assert_any_call("test.txt", 0, b'12345')
    mock_writer.assert_any_call("test.txt", 5, b'67890')
    mock_writer.assert_any_call("test.txt", 10, b'ABCDE')

def test_cleanup_expired(session_manager):
    """Verify creation and cleanup of expired sessions."""
    uid = session_manager.create_session("expires.txt", 100)
    time.sleep(1.1)  # Wait > TTL (1.0)
    session_manager.cleanup_expired_sessions()
    assert session_manager.get_session(uid) is None
