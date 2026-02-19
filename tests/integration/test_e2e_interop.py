"""
End-to-End Interop Tests for Day 5 (Task System).
Verifies strict Client <-> Server contract alignment using AgentClient and Server Dispatcher.
"""
import io
import json
import os
import pytest
import shutil
import tempfile
from unittest.mock import MagicMock

from client.agent_client import AgentClient
from common.app_envelope import encode_message, decode_header, HEADER_SIZE
from common.constants import (
    OP_TASK_SEARCH_REPORT, 
    PROTOCOL_VERSION
)
from server.agent.dispatcher import Dispatcher
from server.agent.validations import PolicyGuard
from server.agent.idempotency import IdempotencyCache

class DirectTransport:
    """
    Simulates a network transport by directly calling the Server Dispatcher.
    Handles framing (simulated) to ensure AgentClient logic (framing/unframing) works.
    """
    def __init__(self, server_dispatcher):
        self.dispatcher = server_dispatcher
        self.response_buffer = b""
        self.connected = True

    def connect(self, timeout=None):
        pass

    def send_bytes(self, data: bytes):
        """
        Simulate sending bytes. 
        In real TCP, this is stream. Here we accept full frames for simplicity,
        or we decapsulate and dispatch.
        """
        # We assume AgentClient sends a full frame at once (it does).
        # Decode Header
        if len(data) < HEADER_SIZE:
             raise ValueError("Data too short for header")
             
        header_bytes = data[:HEADER_SIZE]
        header = decode_header(header_bytes)
        payload = data[HEADER_SIZE:]
        
        # Dispatch to Server
        # Dispatcher expects Header Object and Payload Bytes
        response_bytes = self.dispatcher.dispatch(header, payload)
        
        # Store response for receive_exact
        self.response_buffer += response_bytes

    def receive_exact(self, n: int) -> bytes:
        if len(self.response_buffer) < n:
             raise TimeoutError(f"Not enough data in buffer. Want {n}, have {len(self.response_buffer)}")
        
        chunk = self.response_buffer[:n]
        self.response_buffer = self.response_buffer[n:]
        return chunk

    def close(self):
        self.connected = False

@pytest.fixture
def sandbox_root():
    tmp_dir = tempfile.mkdtemp()
    yield tmp_dir
    shutil.rmtree(tmp_dir)

@pytest.fixture
def server_components(sandbox_root):
    policy_guard = PolicyGuard(sandbox_root)
    idempotency = IdempotencyCache()
    # Mock upload session manager as we don't need it for tasks
    dispatcher = Dispatcher(policy_guard, MagicMock(), idempotency)
    return dispatcher, idempotency

@pytest.fixture
def client_stack(server_components):
    dispatcher, _ = server_components
    transport = DirectTransport(dispatcher)
    client = AgentClient(transport=transport)
    return client

def test_e2e_search_report_inline(client_stack, sandbox_root):
    """
    Verify Client sends correct payload and parses inline response.
    """
    # Setup Data
    input_file = os.path.join(sandbox_root, "small.txt")
    with open(input_file, "w") as f:
        f.write("line 1\nmatch this\nline 3")
        
    client = client_stack
    
    # Execute
    result = client.execute(
        OP_TASK_SEARCH_REPORT, 
        input_file=os.path.basename(input_file),
        query="match"
    )
    
    # Verify
    assert result.status == 200
    assert "data" in result.data
    assert "output" in result.data["data"]
    assert "Line 2: match this" in result.data["data"]["output"]

def test_e2e_artifact_fallback_and_retrieval(client_stack, sandbox_root):
    """
    Verify Client handles 'artifact_path' response by automatically triggering GET.
    """
    # Setup Large Data (>64KB Output)
    input_file = os.path.join(sandbox_root, "large.txt")
    with open(input_file, "w") as f:
        # Write lines that will produce > 64KB output
        # 70KB output
        padding = "x" * 60
        for i in range(2000):
            f.write(f"match line {i} {padding}\n")
            
    client = client_stack
    
    # Execute
    # This should trigger SEARCH -> Server Detects Large Output -> Writes Artifact -> Returns artifact_path -> Client sees it -> Client GETs it.
    result = client.execute(
        OP_TASK_SEARCH_REPORT,
        input_file=os.path.basename(input_file),
        query="match"
    )
    
    # Verify
    assert result.status == 200
    
    # Check that client logic "saved locally" logic ran
    # The TaskHandler returns metadata about the local download
    assert "artifact_local_path" in result.data
    local_path = result.data["artifact_local_path"]
    
    # Verify content of the downloaded file
    assert os.path.exists(local_path)
    with open(local_path, "r") as f:
        content = f.read()
        assert len(content) > 64 * 1024
        assert "match line 0" in content
        assert "match line 500" in content
        assert "... (Truncated)" in content
        
    # Cleanup local file (it's created in CWD by the client handler)
    if os.path.exists(local_path):
        os.remove(local_path)

def test_e2e_server_side_streaming_trigger(client_stack, sandbox_root):
    """
    Verify Server uses STREAM mode for large input files (Schema alignment check).
    Server logic relies on 'input_file' key now. if it fails to find key, it defaults to MEMORY.
    We check logs or we check behavior (memory usage handles unlimited?). 
    Hard to check internals from E2E, but we can check if it works for a file > 256KB.
    """
    input_file = os.path.join(sandbox_root, "huge_input.txt")
    # 300KB file
    with open(input_file, "w") as f:
        f.write("x" * (300 * 1024))
        f.write("\nmatch at end")
        
    client = client_stack
    
    # Execute
    result = client.execute(
        OP_TASK_SEARCH_REPORT,
        input_file=os.path.basename(input_file),
        query="match"
    )
    
    assert result.status == 200
    # Output should be small (just one line), so inline.
    # But PLANNER execution mode should have been STREAM. 
    # (Implicitly verified by it not crashing if we blocked memory reading, but here we just verify it works).
    assert "output" in result.data["data"]
    assert "match at end" in result.data["data"]["output"]

def test_e2e_idempotency_replay(client_stack, sandbox_root):
    """
    Verify Client sending same request_id gets cached response.
    """
    input_file = os.path.join(sandbox_root, "replay_src.txt")
    with open(input_file, "w") as f:
        f.write("content")
        
    client = client_stack
    req_id = 9999
    
    # First Call
    res1 = client.execute(
        OP_TASK_SEARCH_REPORT,
        input_file=os.path.basename(input_file),
        query="content",
        request_id_override=req_id
    )
    
    assert res1.status == 200
    
    # Second Call
    res2 = client.execute(
        OP_TASK_SEARCH_REPORT,
        input_file=os.path.basename(input_file),
        query="content",
        request_id_override=req_id
    )
    
    assert res2.status == 200
    assert res1.data == res2.data
