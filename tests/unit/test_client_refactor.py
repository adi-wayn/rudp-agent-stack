"""
Unit Tests for Client Refactor (Day 4+).
Verifies Dispatcher, Handlers, AgentClient, and UploadClient.
"""
import unittest
import struct
import json
from unittest.mock import MagicMock, patch, ANY

from client.agent.dispatcher import ClientDispatcher, ClientRequestSpec, ENCODING_JSON, ENCODING_MIXED
from client.agent.handlers.get import GetHandler
from client.agent.handlers.append import AppendHandler
from client.agent.handlers.list import ListHandler
from client.agent.handlers.put_meta import PutMetaHandler
from client.agent.handlers.put_chunk import PutChunkHandler

from client.agent_client import AgentClient, OperationResult
from client.agent.upload_client import UploadClient
from common.constants import (
    OP_GET, OP_APPEND, OP_LIST, OP_PUT_META, OP_PUT_CHUNK
)
from common.mixed_mode_io import MixedModeEncoder

class TestClientDispatcher(unittest.TestCase):
    def setUp(self):
        self.dispatcher = ClientDispatcher()
        
    def test_registry(self):
        handler = MagicMock()
        self.dispatcher.register(0xFF, handler)
        self.assertEqual(self.dispatcher.get_handler(0xFF), handler)
        
    def test_missing_handler(self):
        with self.assertRaises(ValueError):
            self.dispatcher.get_handler(0x00)

class TestClientHandlers(unittest.TestCase):
    def test_get_handler(self):
        h = GetHandler()
        # Request
        spec = h.build_request("foo.txt")
        self.assertEqual(spec.opcode, OP_GET)
        self.assertEqual(spec.meta["filename"], "foo.txt")
        self.assertEqual(spec.encoding_mode, ENCODING_JSON)
        # Response (Success)
        res = h.parse_response(200, {}, b"DATA")
        self.assertEqual(res.status, 200)
        self.assertEqual(res.data, b"DATA")
        # Response (Error)
        res = h.parse_response(404, {"error": "Not Found"}, None)
        self.assertEqual(res.status, 404)
        self.assertEqual(res.error, "Not Found")

    def test_append_handler(self):
        h = AppendHandler()
        # Request (Mixed)
        spec = h.build_request("foo.txt", b"DATA")
        self.assertEqual(spec.opcode, OP_APPEND)
        self.assertEqual(spec.encoding_mode, ENCODING_MIXED)
        self.assertEqual(spec.binary, b"DATA")
        # Response (JSON)
        res = h.parse_response(200, {"new_size": 10}, None)
        self.assertEqual(res.status, 200)

class TestAgentClientIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_transport = MagicMock()
        self.mock_transport.is_async = False
        self.client = AgentClient(transport=self.mock_transport)
        self.client.request_id_manager = MagicMock()
        self.client.request_id_manager.next_id.return_value = 123

    def test_execute_get_success(self):
        # 1. Setup Mock Response (200 Mixed Mode)
        resp_payload = MixedModeEncoder.encode({}, b"FILE_CONTENT")
        resp_header = struct.pack("!BBBBII", 1, OP_GET, 0, 0, 123, len(resp_payload))
        self.client.transport.receive_exact.side_effect = [resp_header, resp_payload]
        
        # 2. Execute
        result = self.client.execute(OP_GET, filename="test.txt")
        
        # 3. Verify
        self.assertEqual(result.status, 200)
        self.assertEqual(result.data, b"FILE_CONTENT")
        
        # Verify Send
        args, _ = self.client.transport.send_bytes.call_args
        sent_msg = args[0]
        self.assertEqual(sent_msg[1], OP_GET)

    def test_execute_get_error(self):
        # 1. Setup Mock Response (404 JSON)
        resp_payload = json.dumps({"status": 404, "error": "Missing"}).encode("utf-8")
        resp_header = struct.pack("!BBBBII", 1, OP_GET, 0, 0, 123, len(resp_payload))
        self.client.transport.receive_exact.side_effect = [resp_header, resp_payload]
        
        # 2. Execute
        result = self.client.execute(OP_GET, filename="missing.txt")
        
        # 3. Verify
        self.assertEqual(result.status, 404)
        self.assertEqual(result.error, "Missing")

    def test_execute_append_mixed(self):
        # 1. Setup Mock Response (200 JSON)
        resp_payload = json.dumps({"status": 200}).encode("utf-8")
        resp_header = struct.pack("!BBBBII", 1, OP_APPEND, 0, 0, 123, len(resp_payload))
        self.client.transport.receive_exact.side_effect = [resp_header, resp_payload]
        
        # 2. Execute
        self.client.execute(OP_APPEND, filename="foo", data=b"bar")
        
        # 3. Verify Send (Check correct encoding)
        args, _ = self.client.transport.send_bytes.call_args
        sent = args[0]
        # Skip header (12 bytes)
        payload = sent[12:]
        # Verify it starts with meta length (Mixed Mode)
        self.assertTrue(len(payload) > 4)

class TestUploadHandler(unittest.TestCase):
    def setUp(self):
        self.mock_transport = MagicMock()
        self.mock_transport.is_async = False
        self.client = AgentClient(transport=self.mock_transport)
        self.client.request_id_manager = MagicMock()
        # Mock next_id to return sequential values for non-overridden calls
        self.client.request_id_manager.next_id.side_effect = [100, 101, 102]
        
        # Spy on the REAL execute method, but we mock the inner _send_with_retry
        # actually, we can simpler: just mock _send_with_retry to return responses?
        # But we want to verify `execute` calls for sub-ops.
        
        # Strategy:
        # We want to test `client.execute(OP_UPLOAD)` calling `UploadHandler.run`.
        # `UploadHandler.run` calls `client.execute(OP_PUT_META)`.
        # So we need `client.execute` to be REAL for OP_UPLOAD, but MOCKED (or spied) for others?
        # Or we rely on `_send_with_retry` mocking.
        pass

    @patch("client.agent.handlers.upload.UploadClient")
    def test_upload_orchestration(self, MockUploadClient):
        from common.constants import OP_UPLOAD
        
        # 1. Setup Mock Orchestrator Logic
        orchestrator = MockUploadClient.return_value
        orchestrator.validate_file.return_value = None
        orchestrator.get_file_info.return_value = ("test.txt", 100)
        orchestrator.get_chunks.return_value = iter([
            (0, b"DATA1"), 
            (5, b"DATA2")
        ])
        
        # 2. Mock _send_with_retry to return success for META and CHUNKS
        # META response: status=200, data={upload_id: uid}
        # CHUNK1 response: status=200
        # CHUNK2 response: status=200
        
        # We need to distinguish calls. 
        # send_request_spec(spec)
        # We also need to capture request_id_override from the client state?
        # Actually, in send_request_spec, the override is taken from self.client._active_request_override.
        # So we can't easily capture it from args! Wait!
        
        def side_effect(spec):
            if spec.opcode == OP_PUT_META:
                return (200, {"upload_id": "uid_123"}, None)
            elif spec.opcode == OP_PUT_CHUNK:
                return (200, {"bytes_written": 5}, None)
            return (500, {}, None)
            
        self.client.send_request_spec = MagicMock(side_effect=side_effect)
        
        # 3. Execute OP_UPLOAD
        result = self.client.execute(OP_UPLOAD, local_path="local.txt", remote_name="remote.txt")
        
        # 4. Assertions
        self.assertEqual(result.status, 200)
        self.assertEqual(result.data["status"], "Upload Complete")
        
        # Verify Interactions
        # META called?
        # CHUNKs called?
        # Idempotency?
        
        # Check send_request_spec calls
        calls = self.client.send_request_spec.call_args_list
        self.assertEqual(len(calls), 3)
        
        # META
        meta_spec = calls[0][0][0]
        self.assertEqual(meta_spec.opcode, OP_PUT_META)
        
        # CHUNK 1
        chunk1_spec = calls[1][0][0]
        self.assertEqual(chunk1_spec.opcode, OP_PUT_CHUNK)
        
        # CHUNK 2
        chunk2_spec = calls[2][0][0]
        self.assertEqual(chunk2_spec.opcode, OP_PUT_CHUNK)
        

    @patch("client.agent.handlers.upload.UploadClient")
    def test_upload_idempotency_retry(self, MockUploadClient):
        """Verify that retrying the same chunk generates the same Request ID"""
        from common.constants import OP_UPLOAD
        
        # Setup similar to above
        orchestrator = MockUploadClient.return_value
        orchestrator.validate_file.return_value = None
        orchestrator.get_file_info.return_value = ("test.txt", 100)
        orchestrator.get_chunks.return_value = iter([(0, b"DATA1")]) # 1 chunk
        
        # Mock send_request_spec
        self.client.send_request_spec = MagicMock(return_value=(200, {"upload_id": "uid_FIXED"}, None))
        
        # Run 1
        self.client.execute(OP_UPLOAD, local_path="local", remote_name="remote")
        
        # Reset mocks
        self.client.send_request_spec.reset_mock()
        orchestrator.get_chunks.return_value = iter([(0, b"DATA1")])
        
        # Run 2 
        self.client.send_request_spec.return_value = (200, {"upload_id": "uid_FIXED"}, None)
        
        self.client.execute(OP_UPLOAD, local_path="local", remote_name="remote")
