"""
Unit Tests for AgentClient Day 4 Compliance.
Verifies packet construction and response parsing for LIST, GET, APPEND.
"""
import json
import unittest
import struct
from unittest.mock import MagicMock, patch

from client.agent_client import AgentClient
from common.mixed_mode_io import MixedModeEncoder
from common.constants import OP_LIST, OP_GET, OP_APPEND
from common.app_envelope import encode_message

class TestAgentClientDay4(unittest.TestCase):
    def setUp(self):
         self.client = AgentClient("127.0.0.1", 8080)
         self.client.transport = MagicMock()
         self.client.request_id_manager = MagicMock()
         self.client.request_id_manager.next_id.return_value = 1

    def test_list_files(self):
        # Setup Mock Response
        # Header: Version=1, Op=LIST, Flags=0, Res=0, ReqID=1, Len=...
        # Payload: JSON { "files": [...] }
        resp_payload = json.dumps({"files": [{"name": "a.txt"}]}).encode("utf-8")
        resp_header = struct.pack("!BBBBII", 1, OP_LIST, 0, 0, 1, len(resp_payload))
        
        self.client.transport.receive_exact.side_effect = [resp_header, resp_payload]
        
        # Execute
        files = self.client.list_files()
        
        # Verify Request
        # Expect OP_LIST, Payload b"{}"
        args, _ = self.client.transport.send_bytes.call_args
        sent_data = args[0]
        # Header is 12 bytes. Payload starts at 12.
        self.assertEqual(sent_data[1], OP_LIST)
        self.assertEqual(sent_data[12:], b"{}")
        
        # Verify Response Parsing
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["name"], "a.txt")

    def test_get_file_success(self):
        # 200 OK -> Mixed Mode Response
        meta = {"status": 200, "filename": "test.txt"}
        binary = b"FILE CONTENT"
        resp_payload = MixedModeEncoder.encode(meta, binary)
        resp_header = struct.pack("!BBBBII", 1, OP_GET, 0, 0, 1, len(resp_payload))
        
        self.client.transport.receive_exact.side_effect = [resp_header, resp_payload]
        
        # Execute
        content = self.client.get_file("test.txt")
        
        # Verify Request
        # Expect OP_GET, Payload JSON {"filename": "test.txt"}
        args, _ = self.client.transport.send_bytes.call_args
        sent_data = args[0]
        self.assertEqual(sent_data[1], OP_GET)
        req_payload = json.loads(sent_data[12:].decode("utf-8"))
        self.assertEqual(req_payload["filename"], "test.txt")
        
        # Verify Result
        self.assertEqual(content, b"FILE CONTENT")

    def test_get_file_error_404(self):
        # 404 -> JSON Only Response
        resp_payload = json.dumps({"status": 404, "error": "Not Found"}).encode("utf-8")
        resp_header = struct.pack("!BBBBII", 1, OP_GET, 0, 0, 1, len(resp_payload))
        
        self.client.transport.receive_exact.side_effect = [resp_header, resp_payload]
        
        # Execute
        with self.assertRaises(ValueError) as cm:
            self.client.get_file("missing.txt")
            
        self.assertIn("GET failed: 404", str(cm.exception))

    def test_append_file(self):
        # Request: Mixed Mode
        # Response: JSON 200
        resp_payload = json.dumps({"status": 200, "new_size": 50}).encode("utf-8")
        resp_header = struct.pack("!BBBBII", 1, OP_APPEND, 0, 0, 1, len(resp_payload))
        
        self.client.transport.receive_exact.side_effect = [resp_header, resp_payload]
        
        # Execute
        data = b"APPEND DATA"
        result = self.client.append_file("test.txt", data)
        
        # Verify Request
        args, _ = self.client.transport.send_bytes.call_args
        sent_data = args[0]
        self.assertEqual(sent_data[1], OP_APPEND)
        
        # Check Mixed Mode Payload
        req_payload = sent_data[12:]
        # Decode to verify
        from common.mixed_mode_io import MixedModeDecoder
        meta, binary = MixedModeDecoder.decode(req_payload)
        self.assertEqual(meta["filename"], "test.txt")
        self.assertEqual(binary, data)
        
        # Verify Response
        self.assertEqual(result["new_size"], 50)
