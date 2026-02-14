"""
Unit tests for upload handlers.
"""
import pytest
import json
import os
from unittest.mock import MagicMock, patch
from common.app_envelope import AppHeader
from common.constants import OP_PUT_META, OP_PUT_CHUNK, MAX_FILE_SIZE
from server.agent.validations import PolicyGuard
from server.agent.upload_session import UploadSessionManager
from server.agent.handlers.put import handle_put_meta, handle_put_chunk

@pytest.fixture
def setup_components(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    policy_guard = PolicyGuard(str(sandbox))
    session_manager = UploadSessionManager()
    return policy_guard, session_manager, sandbox

def test_handle_put_meta_success(setup_components):
    policy_guard, session_manager, sandbox = setup_components
    
    payload = json.dumps({
        "filename": "new_file.txt",
        "total_size": 100
    }).encode('utf-8')
    
    header = AppHeader(1, OP_PUT_META, 0, 0, 123, len(payload))
    
    result = handle_put_meta(header, payload, policy_guard, session_manager)
    
    assert "upload_id" in result
    assert result["status"] == "ready"
    assert (sandbox / "new_file.txt").exists()
    
def test_handle_put_meta_too_large(setup_components):
    policy_guard, session_manager, _ = setup_components
    
    payload = json.dumps({
        "filename": "huge.txt",
        "total_size": MAX_FILE_SIZE + 1
    }).encode('utf-8')
    
    header = AppHeader(1, OP_PUT_META, 0, 0, 123, len(payload))
    
    with pytest.raises(ValueError, match="exceeds limit"):
        handle_put_meta(header, payload, policy_guard, session_manager)

def test_handle_put_chunk_success(setup_components):
    policy_guard, session_manager, sandbox = setup_components
    
    # 1. Create Session
    meta_payload = json.dumps({"filename": "data.bin", "total_size": 10}).encode('utf-8')
    handle_put_meta(AppHeader(1, OP_PUT_META, 0, 0, 1, len(meta_payload)), meta_payload, policy_guard, session_manager)
    
    upload_id = list(session_manager.sessions.keys())[0]
    
    # 2. Send Chunk
    chunk_data = b'0123456789'
    chunk_meta = json.dumps({
        "upload_id": upload_id,
        "offset": 0,
        "chunk_len": 10
    })
    full_payload = chunk_meta.encode('utf-8') + chunk_data
    
    header = AppHeader(1, OP_PUT_CHUNK, 0, 0, 2, len(full_payload))
    
    result = handle_put_chunk(header, full_payload, policy_guard, session_manager)
    
    assert result["complete"] is True
    assert result["bytes_written"] == 10
    
    # Verify file content
    with open(sandbox / "data.bin", "rb") as f:
        assert f.read() == b'0123456789'

def test_handle_put_chunk_missing_session(setup_components):
    policy_guard, session_manager, _ = setup_components
    
    chunk_meta = json.dumps({
        "upload_id": "fake-id",
        "offset": 0,
        "chunk_len": 5
    })
    payload = chunk_meta.encode('utf-8') + b'12345'
    header = AppHeader(1, OP_PUT_CHUNK, 0, 0, 1, len(payload))
    
    with pytest.raises(ValueError, match="Session fake-id not found"):
        handle_put_chunk(header, payload, policy_guard, session_manager)
