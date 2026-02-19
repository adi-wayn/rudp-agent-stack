"""
Integration Tests for Task Execution.
Validates the full pipeline: Dispatcher -> Task Handler -> Planner -> ToolDispatcher.
"""
import json
import os
import pytest
import shutil
import tempfile
from unittest.mock import MagicMock

from common.app_envelope import AppHeader
from common.constants import (
    OP_TASK_SEARCH_REPORT,
    OP_TASK_FILTER_LINES,
    OP_TASK_HASH_AND_STORE,
    PROTOCOL_VERSION
)
from server.agent.dispatcher import Dispatcher
from server.agent.validations import PolicyGuard
from server.agent.upload_session import UploadSessionManager
from server.agent.idempotency import IdempotencyCache

@pytest.fixture
def sandbox_root():
    """Create a temp sandbox directory."""
    tmp_dir = tempfile.mkdtemp()
    yield tmp_dir
    shutil.rmtree(tmp_dir)

@pytest.fixture
def policy_guard(sandbox_root):
    return PolicyGuard(sandbox_root)

@pytest.fixture
def dispatcher(policy_guard):
    idempotency = IdempotencyCache()
    return Dispatcher(policy_guard, MagicMock(), idempotency)

def create_header(opcode, request_id, payload):
    return AppHeader(
        version=PROTOCOL_VERSION,
        opcode=opcode,
        flags=0,
        reserved=0,
        request_id=request_id,
        payload_len=len(payload)
    )

def test_task_search_report_inline(dispatcher, sandbox_root):
    """Test SEARCH_REPORT returning inline result."""
    # Setup File
    target_file = os.path.join(sandbox_root, "search_me.txt")
    with open(target_file, "w") as f:
        f.write("line 1\nmatch foo\nline 3\nmatch bar")
        
    payload = json.dumps({
        "input_file": os.path.basename(target_file),
        "query": "match"
    }).encode()
    
    header = create_header(OP_TASK_SEARCH_REPORT, 1001, payload)
    
    # Execute
    response = dispatcher.dispatch(header, payload)
    
    # Validate
    # Response is binary envelope. Dispatch returns bytes.
    # But wait, Dispatcher.dispatch returns bytes (Envelope).
    # We need to decode it to check content.
    # For integration test, we trust ResponseBuilder logic, 
    # but to verify the content we'd need to decode header + payload.
    # Or we can verify the ToolDispatcher executed correctly by mocking?
    # No, this is integration. Let's decode the response envelope.
    
    from common.app_envelope import decode_header, HEADER_SIZE
    
    resp_header = decode_header(response[:HEADER_SIZE])
    resp_payload = response[HEADER_SIZE:]
    resp_data = json.loads(resp_payload.decode())
    
    assert resp_header.opcode == OP_TASK_SEARCH_REPORT
    assert resp_header.request_id == 1001
    # ResponseBuilder wraps result in "data"
    assert "output" in resp_data["data"]
    assert "Line 2: match foo" in resp_data["data"]["output"]
    assert "Line 4: match bar" in resp_data["data"]["output"]

def test_task_filter_lines_outfile(dispatcher, sandbox_root):
    """Test FILTER_LINES writing to a file."""
    input_file = os.path.join(sandbox_root, "input.txt")
    output_file = os.path.join(sandbox_root, "output.txt")
    
    with open(input_file, "w") as f:
        f.write("apple\nbanana\ncherry\ndate")
        
    payload = json.dumps({
        "input_file": os.path.basename(input_file),
        "query": "a",
        "options": {"format": "lines"},
        "out_file": os.path.basename(output_file)
    }).encode()
    
    header = create_header(OP_TASK_FILTER_LINES, 2002, payload)
    
    response = dispatcher.dispatch(header, payload)
    
    assert os.path.exists(output_file)
    with open(output_file, "r") as f:
        content = f.read()
        assert "apple" in content
        assert "banana" in content
        assert "date" in content
        assert "cherry" not in content

def test_task_idempotency_replay(dispatcher, sandbox_root):
    """Test that replaying a side-effect task returns cached result without re-execution."""
    # HASH_AND_STORE has side effects
    target_file = os.path.join(sandbox_root, "data.bin")
    out_file = os.path.join(sandbox_root, "hash.txt")
    with open(target_file, "wb") as f:
        f.write(b"12345")
        
    payload = json.dumps({
        "input_file": os.path.basename(target_file),
        "out_file": os.path.basename(out_file)
    }).encode()
    
    header = create_header(OP_TASK_HASH_AND_STORE, 3003, payload)
    
    # First Call
    resp1 = dispatcher.dispatch(header, payload)
    
    # Verify file created
    assert os.path.exists(out_file)
    mtime1 = os.path.getmtime(out_file)
    
    # Wait a bit or ensure fs resolution
    # Instead of waiting, delete the file to prove re-execution didn't happen!
    os.remove(out_file)
    
    # Second Call (Replay)
    resp2 = dispatcher.dispatch(header, payload)
    
    # Should return cached success, BUT NOT re-create the file
    assert resp1 == resp2
    assert not os.path.exists(out_file) # Proof it didn't run again

def test_fallback_artifact_generation(dispatcher, sandbox_root):
    """Test that large output falls back to artifact."""
    target_file = os.path.join(sandbox_root, "large_search.txt")
    # Create file large enough to exceed 64KB inline limit in output
    # 64KB limit.
    # Write 70KB of matching lines
    with open(target_file, "w") as f:
        # Make lines longer to ensure 1000 lines exceed 64KB
        # 1000 lines * 70 bytes = 70KB > 64KB
        padding = "x" * 60
        for i in range(2000): # 2000 lines to be safe
            f.write(f"match check line {i} {padding}\n")
            
    payload = json.dumps({
        "input_file": os.path.basename(target_file),
        "query": "match"
    }).encode()
    
    header = create_header(OP_TASK_SEARCH_REPORT, 4004, payload)
    
    # Dispatch
    # We must ensure artifacts dir is writable in sandbox root?
    # ToolDispatcher writes to "artifacts/..." relative to CWD.
    # Integration tests run in project root, so "artifacts" will be created there.
    # To avoid pollution, we should mock CWD or configure artifact dir.
    # But `ToolDispatcher` has hardcoded "artifacts".
    # For now, we accept it creates "artifacts" in run directory, request cleanup.
    # Actually, verify "artifact_path" is in response.
    
    try:
        response = dispatcher.dispatch(header, payload)
        
        from common.app_envelope import decode_header, HEADER_SIZE
        resp_payload = response[HEADER_SIZE:]
        resp_data = json.loads(resp_payload.decode())
        
        # Should NOT have "output" (too big)
        # Should have "artifact_path"
        # Check inside 'data'
        result_data = resp_data.get("data", {})
        assert "artifact_path" in result_data
        assert "output" not in result_data
        
        # Cleanup
        artifact_path = result_data["artifact_path"]
        if os.path.exists(artifact_path):
            os.remove(artifact_path)
            # Try to remove parent dirs if empty
            try:
                os.removedirs(os.path.dirname(artifact_path))
            except:
                pass
                
    finally:
        pass
