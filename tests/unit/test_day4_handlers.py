"""
Unit Tests for Day 4 File Operations.
Handlers: GET, APPEND, LIST.
Constraints: Mixed Mode, Size Limits, Idempotency.
"""
import json
import struct
import os
import unittest
from unittest.mock import MagicMock, patch

from common.mixed_mode_io import MixedModeEncoder, MixedModeDecoder
from common.app_envelope import AppHeader
from common.errors import ErrorCode
from common.constants import MAX_FILE_SIZE, OP_GET, OP_APPEND, OP_LIST

from server.agent.validations import PolicyGuard
from server.agent.handlers.get import handle_get, MAX_INLINE_SIZE
from server.agent.handlers.append import handle_append
from server.agent.handlers.list import handle_list
from server.agent.idempotency import IdempotencyCache

class TestMixedModeIO(unittest.TestCase):
    def test_encode_decode(self):
        meta = {"filename": "test.txt", "size": 123}
        binary = b"Hello World"
        
        encoded = MixedModeEncoder.encode(meta, binary)
        
        # Verify Format: [Len][Meta][Binary]
        meta_bytes = json.dumps(meta).encode("utf-8")
        expected_len = struct.pack("!I", len(meta_bytes))
        self.assertTrue(encoded.startswith(expected_len))
        
        decoded_meta, decoded_bin = MixedModeDecoder.decode(encoded)
        self.assertEqual(decoded_meta, meta)
        self.assertEqual(decoded_bin, binary)

    def test_decode_invalid_length(self):
        with self.assertRaises(ValueError):
             MixedModeDecoder.decode(b"\x00\x00\x00\x10Short")

class TestGetHandler(unittest.TestCase):
    def setUp(self):
        self.policy_guard = MagicMock(spec=PolicyGuard)
        self.header = AppHeader(1, OP_GET, 0, 0, 12345, 100)
    
    @patch("server.agent.handlers.get.os.path.exists")
    @patch("server.agent.handlers.get.os.path.getsize")
    @patch("builtins.open")
    def test_get_success(self, mock_open, mock_getsize, mock_exists):
        # Setup
        self.policy_guard.validate_path.return_value = "/sandbox/test.txt"
        mock_exists.return_value = True
        mock_getsize.return_value = 500 # < 64KB
        
        mock_file = MagicMock()
        mock_file.read.return_value = b"DATA"
        mock_open.return_value.__enter__.return_value = mock_file
        
        payload = json.dumps({"filename": "test.txt"}).encode("utf-8")
        
        # Execute
        result = handle_get(self.header, payload, self.policy_guard)
        
        # Verify
        self.assertEqual(result["filename"], "test.txt")
        self.assertEqual(result["size"], 500)
        self.assertEqual(result["BINARY_CONTENT"], b"DATA")
        
    def test_get_missing_payload(self):
        with self.assertRaises(ValueError):
            handle_get(self.header, b"", self.policy_guard)
            
    def test_get_not_found(self):
        self.policy_guard.validate_path.return_value = "/sandbox/err.txt"
        with patch("server.agent.handlers.get.os.path.exists", return_value=False):
            payload = json.dumps({"filename": "err.txt"}).encode("utf-8")
            with self.assertRaises(FileNotFoundError):
                 handle_get(self.header, payload, self.policy_guard)

    @patch("server.agent.handlers.get.os.path.exists", return_value=True)
    @patch("server.agent.handlers.get.os.path.getsize")
    def test_get_too_large(self, mock_getsize, mock_exists):
        self.policy_guard.validate_path.return_value = "/sandbox/big.txt"
        mock_getsize.return_value = MAX_FILE_SIZE + 1
        
        payload = json.dumps({"filename": "big.txt"}).encode("utf-8")
        
        with self.assertRaises(ValueError) as cm:
            handle_get(self.header, payload, self.policy_guard)
        self.assertIn("too large", str(cm.exception))

    @patch("server.agent.handlers.get.os.path.exists", return_value=True)
    @patch("server.agent.handlers.get.os.path.getsize")
    def test_get_inline_limit(self, mock_getsize, mock_exists):
        self.policy_guard.validate_path.return_value = "/sandbox/inline.txt"
        mock_getsize.return_value = MAX_INLINE_SIZE + 1
        
        payload = json.dumps({"filename": "inline.txt"}).encode("utf-8")
        
        with self.assertRaises(ValueError) as cm:
            handle_get(self.header, payload, self.policy_guard)
        self.assertIn("inline retrieval", str(cm.exception))

class TestAppendHandler(unittest.TestCase):
    def setUp(self):
        self.policy_guard = MagicMock(spec=PolicyGuard)
        self.cache = MagicMock(spec=IdempotencyCache)
        self.header = AppHeader(1, OP_APPEND, 0, 0, 12345, 100)
    
    @patch("server.agent.handlers.append.os.path.exists")
    @patch("server.agent.handlers.append.os.path.getsize")
    @patch("builtins.open")
    def test_append_success(self, mock_open, mock_getsize, mock_exists):
        # Setup
        self.policy_guard.validate_path.return_value = "/sandbox/append.txt"
        mock_exists.return_value = True
        mock_getsize.side_effect = [100, 110] # Before, After
        
        payload = MixedModeEncoder.encode({"filename": "append.txt"}, b"0123456789")
        
        # Execute
        result = handle_append(self.header, payload, self.policy_guard, self.cache)
        
        # Verify
        mock_open.assert_called_with("/sandbox/append.txt", "ab")
        self.assertEqual(result["new_size"], 110)

    @patch("server.agent.handlers.append.os.path.exists", return_value=True)
    @patch("server.agent.handlers.append.os.path.getsize")
    def test_append_overflow(self, mock_getsize, mock_exists):
        self.policy_guard.validate_path.return_value = "/sandbox/full.txt"
        mock_getsize.return_value = MAX_FILE_SIZE - 5
        
        # Try to append 10 bytes
        payload = MixedModeEncoder.encode({"filename": "full.txt"}, b"0123456789")
        
        with self.assertRaises(ValueError) as cm:
             handle_append(self.header, payload, self.policy_guard, self.cache)
        self.assertIn("exceed max", str(cm.exception))

class TestListHandler(unittest.TestCase):
    def setUp(self):
        self.policy_guard = MagicMock(spec=PolicyGuard)
        self.policy_guard.sandbox_root = "/sandbox"
    
    @patch("os.stat")
    def test_list_metadata(self, mock_stat):
        # Setup
        self.policy_guard.list_sandbox.return_value = ["b.txt", "a.txt"]
        
        stat_a = MagicMock()
        stat_a.st_size = 100
        stat_a.st_mtime = 1000.0
        
        stat_b = MagicMock()
        stat_b.st_size = 200
        stat_b.st_mtime = 2000.0
        
        def side_effect(path):
            if "a.txt" in path: return stat_a
            if "b.txt" in path: return stat_b
            raise OSError
            
        mock_stat.side_effect = side_effect
        
        # Execute
        result = handle_list(None, self.policy_guard)
        
        # Verify
        files = result["files"]
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0]["size"], 100)
        self.assertEqual(files[1]["name"], "b.txt")

class TestAgentServerIdempotency(unittest.TestCase):
    def setUp(self):
        # We need to test AgentServer's process_request logic
        # But AgentServer is integration-heavy.
        # Let's mock the internal cache interaction.
        from server.agent_server import AgentServer
        from server.agent.idempotency import IdempotencyCache

        with patch("server.agent_server.PolicyGuard"), \
             patch("server.agent_server.UploadSessionManager"), \
             patch("server.agent_server.Dispatcher") as MockDispatcher:
             
            self.server = AgentServer("/sandbox")
            self.mock_dispatcher = self.server.dispatcher = MagicMock() # Replace real dispatcher
            self.server.idempotency_cache = MagicMock(spec=IdempotencyCache)
            
    def test_append_duplicate_idempotency(self):
        # Verify that if cache returns a response, Dispatcher is NOT called (No validation, No IO)
        
        # Setup
        client_id = "127.0.0.1:12345"
        req_id = 999
        opcode = OP_APPEND
        # Valid header but opcode will be extracted
        header_bytes = struct.pack("!BBBBII", 1, opcode, 0, 0, req_id, 0)
        full_msg = header_bytes
        
        # Case 1: Cache Miss (First Request)
        self.server.idempotency_cache.get_response.return_value = None
        self.mock_dispatcher.dispatch.return_value = b"NEW_RESPONSE"
        
        resp1 = self.server.process_request(client_id, full_msg)
        
        # Verify Dispatcher Called
        self.mock_dispatcher.dispatch.assert_called()
        self.assertEqual(resp1, b"NEW_RESPONSE")
        # Verify Cache Store
        self.server.idempotency_cache.store_response.assert_called()
        
        # Reset Mocks
        self.mock_dispatcher.dispatch.reset_mock()
        self.server.idempotency_cache.store_response.reset_mock()
        
        # Case 2: Cache Hit (Duplicate Request)
        self.server.idempotency_cache.get_response.return_value = b"CACHED_RESPONSE"
        
        # Need to re-trigger get_response call logic
        # process_request calls get_response first
        
        resp2 = self.server.process_request(client_id, full_msg)
        
        # Verify Dispatcher NOT Called (Critical for APPEND safety)
        self.mock_dispatcher.dispatch.assert_not_called()
        self.assertEqual(resp2, b"CACHED_RESPONSE")
