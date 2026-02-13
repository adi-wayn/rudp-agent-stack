"""
Tests for Day 2 Core Pipeline.
Covers:
- RequestContext (Header)
- PolicyGuard
- IdempotencyCache
- Dispatcher
- LIST Handler
- AgentServer Pipeline
- Unified Response Structure
"""
import pytest
import os
import shutil
import json
import struct
import time
from common.app_envelope import encode_header, encode_message, decode_header, HEADER_SIZE
from common.constants import OP_LIST, PROTOCOL_VERSION, MAX_PAYLOAD_LEN
from common.errors import ErrorCode

from server.agent_server import AgentServer
from server.agent.validations import PolicyGuard
from server.agent.idempotency import IdempotencyCache

TEST_SANDBOX = "./test_sandbox_day2"

@pytest.fixture
def sandbox():
    if os.path.exists(TEST_SANDBOX):
        shutil.rmtree(TEST_SANDBOX)
    os.makedirs(TEST_SANDBOX)
    
    # Create some dummy files
    with open(os.path.join(TEST_SANDBOX, "file1.txt"), "w") as f:
        f.write("A")
    with open(os.path.join(TEST_SANDBOX, "file2.log"), "w") as f:
        f.write("B")
        
    yield TEST_SANDBOX
    
    if os.path.exists(TEST_SANDBOX):
        shutil.rmtree(TEST_SANDBOX)

@pytest.fixture
def agent_server(sandbox):
    return AgentServer(sandbox_root=sandbox)

def test_list_success(agent_server, sandbox):
    """
    Test valid LIST request returns correct files in unified JSON structure.
    """
    req_id = 101
    # Create LIST message (Empty Payload)
    req_data = encode_message(OP_LIST, 0, req_id, b'')
    
    # Process
    resp_data = agent_server.process_request("client1", req_data)
    
    # Verify Header
    header = decode_header(resp_data[:HEADER_SIZE])
    assert header.request_id == req_id
    assert header.opcode == OP_LIST
    
    # Verify JSON Payload Structure
    payload = resp_data[HEADER_SIZE:]
    response_json = json.loads(payload.decode("utf-8"))
    
    # Assert Unified Schema: { status, error, data }
    assert "status" in response_json
    assert "data" in response_json
    assert "error" in response_json

    # Status should be OK
    # Note: ErrorCode.OK maps to 200
    assert response_json["status"] == ErrorCode.OK
    assert response_json["error"] is None
    
    files = response_json["data"]
    assert "file1.txt" in files
    assert "file2.log" in files
    assert len(files) == 2

def test_unknown_opcode(agent_server):
    """
    Test unknown opcode returns Error 400 in unified JSON structure.
    """
    req_id = 102
    UNKNOWN_OP = 0x99
    req_data = encode_message(UNKNOWN_OP, 0, req_id, b'')
    
    resp_data = agent_server.process_request("client1", req_data)
    
    header = decode_header(resp_data[:HEADER_SIZE])
    assert header.request_id == req_id
    # ResponseBuilder uses request opcode for correlation.
    assert header.opcode == UNKNOWN_OP 
    
    payload = resp_data[HEADER_SIZE:]
    response_json = json.loads(payload.decode("utf-8"))
    
    assert response_json["status"] == ErrorCode.BAD_REQUEST
    assert "Unknown Opcode" in response_json["error"]
    assert response_json["data"] is None

def test_idempotency(agent_server):
    """
    Test duplicate request returns cached response.
    """
    req_id = 103
    req_data = encode_message(OP_LIST, 0, req_id, b'')
    
    # First Call
    resp1 = agent_server.process_request("client1", req_data)
    
    # Manually Inject a distinguishable fake response to test cache hit
    # Must preserve header structure
    fake_payload = json.dumps({"status": 200, "data": "FAKE"}).encode("utf-8")
    fake_resp = encode_message(OP_LIST, 0, req_id, fake_payload)
    
    agent_server.idempotency_cache.store_response(
        "client1", req_id, OP_LIST, fake_resp
    )
    
    # Second Call
    resp2 = agent_server.process_request("client1", req_data)
    
    assert resp2 == fake_resp

def test_payload_length_mismatch(agent_server):
    """
    Test rejection of payload length mismatch.
    """
    req_id = 104
    # Header says 10 bytes, but send 5
    header = encode_header(PROTOCOL_VERSION, OP_LIST, 0, req_id, 10)
    req_data = header + b'12345'
    
    resp = agent_server.process_request("client1", req_data)
    assert resp == b'' # Should drop/ignore

def test_policy_guard_path_traversal(sandbox):
    """
    Test PolicyGuard rejects traversal.
    """
    pg = PolicyGuard(sandbox)
    
    with pytest.raises(ValueError, match="Subdirectories not allowed"):
        pg.validate_path("subdir/file.txt")
        
    with pytest.raises(ValueError, match="Subdirectories not allowed"):
        pg.validate_path("../secrets.txt")
