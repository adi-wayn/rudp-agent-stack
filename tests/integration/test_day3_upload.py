"""
Integration Test for Day 3: Client Upload Flow.
Verifies PUT_META -> PUT_CHUNK flow against actual server.
Uses TCP transport for reliability baseline.
"""
import unittest
import threading
import time
import os
import shutil
import logging
import socket
from common.constants import AGENT_SERVER_PORT, LOOPBACK_IP
from client.transport.tcp_client import TCPClient
from client.agent.upload_client import UploadClient
from server.agent_server import AgentServer

# Configure logging for test
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestDay3Upload")

TEST_SERVER_PORT = AGENT_SERVER_PORT + 1  # Use different port to avoid conflict if main server running
TEST_SANDBOX_DIR = "./test_sandbox_day3"

from server.transport.tcp_server import TCPServerTransport

class TestDay3UploadFlow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # 1. Clean Sandbox
        if os.path.exists(TEST_SANDBOX_DIR):
            shutil.rmtree(TEST_SANDBOX_DIR)
        os.makedirs(TEST_SANDBOX_DIR)

        # 2. Start Server
        cls.transport = TCPServerTransport(port=TEST_SERVER_PORT, bind_ip=LOOPBACK_IP)
        cls.server = AgentServer(
            sandbox_root=TEST_SANDBOX_DIR,
            transport=cls.transport
        )
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        
        # Give server time to bind
        time.sleep(1)

    @classmethod
    def tearDownClass(cls):
        # Stop Server (AgentServer doesn't have stop() exposed easily in loop, but daemon helps)
        # Ideally we'd close the socket.
        # For now, rely on daemon thread termination at end of process, 
        # or implement stop mechanism if needed.
        pass

    def setUp(self):
        self.client = TCPClient(server_ip=LOOPBACK_IP, server_port=TEST_SERVER_PORT)
        self.client.connect()
        self.uploader = UploadClient(self.client)

    def tearDown(self):
        self.client.close()

    def test_upload_small_file(self):
        """Test uploading a file smaller than one chunk."""
        filename = "small_test.txt"
        content = b"Hello World Day 3"
        local_path = f"tmp_{filename}"
        
        with open(local_path, "wb") as f:
            f.write(content)
            
        success = self.uploader.upload_file(local_path, filename, chunk_size=1024)
        self.assertTrue(success, "Upload failed")
        
        # Verify on Server
        server_path = os.path.join(TEST_SANDBOX_DIR, filename)
        self.assertTrue(os.path.exists(server_path), "File not created on server")
        with open(server_path, "rb") as f:
            self.assertEqual(f.read(), content, "Content mismatch")
            
        os.remove(local_path)

    def test_upload_multi_chunk(self):
        """Test uploading a file spanning multiple chunks."""
        filename = "multi_chunk.bin"
        chunk_size = 1024
        total_size = chunk_size * 5 + 100 # 5 full chunks + 1 partial
        content = os.urandom(total_size)
        local_path = f"tmp_{filename}"
        
        with open(local_path, "wb") as f:
            f.write(content)
            
        # Use small chunk size in uploader to force splitting
        success = self.uploader.upload_file(local_path, filename, chunk_size=chunk_size)
        self.assertTrue(success, "Multi-chunk upload failed")
        
        # Verify
        server_path = os.path.join(TEST_SANDBOX_DIR, filename)
        with open(server_path, "rb") as f:
            self.assertEqual(f.read(), content, "Content mismatch")
            
        os.remove(local_path)

    def test_upload_large_file_check(self):
        """Test behavior near 1MB edge (should pass)."""
        # Create 1MB file (Max allowed)
        filename = "large_1mb.bin"
        size = 1024 * 1024
        content = b'\x00' * size
        local_path = f"tmp_{filename}"
        
        with open(local_path, "wb") as f:
            f.write(content)
            
        success = self.uploader.upload_file(local_path, filename, chunk_size=32768)
        self.assertTrue(success, "1MB upload failed")
        
        server_path = os.path.join(TEST_SANDBOX_DIR, filename)
        self.assertEqual(os.path.getsize(server_path), size)
        
        os.remove(local_path)

if __name__ == "__main__":
    unittest.main()
