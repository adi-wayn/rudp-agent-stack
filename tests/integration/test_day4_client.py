
import unittest
import socket
import threading
import time
import json
import struct
from client.agent_client import AgentClient
from common.app_envelope import encode_message, decode_header, HEADER_SIZE
from common.constants import OP_LIST, OP_GET, OP_APPEND, PROTOCOL_VERSION

class MockServer(threading.Thread):
    """
    Mock Server for testing AgentClient.
    Can be configured to respond in specific ways (partial sends, specific payloads).
    """
    def __init__(self, port):
        super().__init__()
        self.port = port
        print(f"DEBUG: Initializing MockServer on port {port}")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("127.0.0.1", port))
            print("DEBUG: Bind successful")
        except Exception as e:
            print(f"DEBUG: Bind failed: {e}")
            raise
        self.sock.listen(1)
        self.running = True
        self.behavior = None
        self.last_request = None
        self.connection_count = 0

    def run(self):
        print("DEBUG: MockServer thread started")
        while self.running:
            try:
                self.sock.settimeout(0.5)
                client_sock, _ = self.sock.accept()
                self.connection_count += 1
                self.handle_client(client_sock)
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    # Ignore errors during shutdown
                    pass
        print("DEBUG: MockServer thread stopped")

    def handle_client(self, client_sock):
        try:
            # Read Header
            header_data = b""
            while len(header_data) < HEADER_SIZE:
                chunk = client_sock.recv(HEADER_SIZE - len(header_data))
                if not chunk: break
                header_data += chunk
            
            if len(header_data) != HEADER_SIZE:
                return

            header = decode_header(header_data)
            
            # Read Payload
            payload_data = b""
            while len(payload_data) < header.payload_len:
                chunk = client_sock.recv(header.payload_len - len(payload_data))
                if not chunk: break
                payload_data += chunk
                
            self.last_request = {
                "header": header,
                "payload": payload_data
            }

            # Execute behavior
            if self.behavior:
                self.behavior(client_sock, header, payload_data)
                
        except Exception as e:
            print(f"Mock server error: {e}")
        finally:
            client_sock.close()

    def stop(self):
        self.running = False
        self.sock.close()

class TestDay4Client(unittest.TestCase):
    SERVER_PORT = 9999

    @classmethod
    def setUpClass(cls):
        print("DEBUG: setUpClass starting")
        cls.server = MockServer(cls.SERVER_PORT)
        cls.server.start()
        # Give server time to start
        time.sleep(0.1)
        print("DEBUG: setUpClass finished")

    @classmethod
    def tearDownClass(cls):
        print("DEBUG: tearDownClass starting")
        cls.server.stop()
        cls.server.join()
        print("DEBUG: tearDownClass finished")

    def setUp(self):
        self.client = AgentClient("127.0.0.1", self.SERVER_PORT)
        self.server.behavior = None
        self.server.last_request = None
        self.server.connection_count = 0

    def tearDown(self):
        self.client.close()

    def test_list_files(self):
        """Test LIST sends empty payload and parses JSON list."""
        print("DEBUG: Running test_list_files")
        expected_files = ["file1.txt", "file2.log"]
        
        def handle_list(sock, header, payload):
            # Verify payload is empty
            if payload != b"":
                 print("WARNING: Expected empty payload for LIST")
                 
            # Respond with JSON
            resp_payload = json.dumps(expected_files).encode("utf-8")
            response = encode_message(OP_LIST, 0, header.request_id, resp_payload)
            sock.sendall(response)

        self.server.behavior = handle_list
        
        files = self.client.list_files()
        self.assertEqual(files, expected_files)
        # Verify request opcode
        self.assertEqual(self.server.last_request['header'].opcode, OP_LIST)
        self.assertEqual(self.server.last_request['payload'], b"")

    def test_get_file_raw_bytes(self):
        """Test GET returns raw bytes (success)."""
        print("DEBUG: Running test_get_file_raw_bytes")
        file_content = b"This is raw file content. Not JSON."
        
        def handle_get(sock, header, payload):
            # Verify payload is JSON filename
            req = json.loads(payload.decode("utf-8"))
            self.assertEqual(req['filename'], "test.txt")
            
            # Respond with raw bytes
            response = encode_message(OP_GET, 0, header.request_id, file_content)
            sock.sendall(response)

        self.server.behavior = handle_get
        
        result = self.client.get_file("test.txt")
        self.assertEqual(result, file_content)

    def test_append_file_mixed_payload(self):
        """Test APPEND constructs mixed JSON+Binary payload."""
        print("DEBUG: Running test_append_file_mixed_payload")
        filename = "append.test"
        data_to_append = b"Appended Data"
        
        def handle_append(sock, header, payload):
            # Verify mixed payload
            # 1. Starts with JSON
            decoder = json.JSONDecoder()
            meta, idx = decoder.raw_decode(payload.decode("utf-8"))
            
            self.assertEqual(meta['filename'], filename)
            # Ensure no "len" field if we decided so (Plan says remove it)
            self.assertNotIn("len", meta)
            
            # 2. Binary follows immediately
            # We need to find byte offset of idx. 
            # Since we encoded with strict separators, we can guess or re-encode.
            # But simpler: The JSON part should be valid utf-8.
            # verify payload[byte_len_of_json:] == data_to_append
            
            # Reconstruct JSON bytes to find length
            meta_bytes = json.dumps(meta, separators=(',', ':')).encode('utf-8')
            self.assertTrue(payload.startswith(meta_bytes))
            
            binary_part = payload[len(meta_bytes):]
            self.assertEqual(binary_part, data_to_append)
            
            # Respond
            resp_payload = json.dumps({"status": 200, "message": "OK"}).encode("utf-8")
            response = encode_message(OP_APPEND, 0, header.request_id, resp_payload)
            sock.sendall(response)

        self.server.behavior = handle_append
        
        resp = self.client.append_file(filename, data_to_append)
        self.assertEqual(resp['status'], 200)

    def test_tcp_framing_partial(self):
        """Test client handles split TCP packets (Partial Reads)."""
        print("DEBUG: Running test_tcp_framing_partial")
        response_data = json.dumps(["partial"]).encode("utf-8")
        
        def handle_split_send(sock, header, payload):
            full_response = encode_message(OP_LIST, 0, header.request_id, response_data)
            
            # Split into tiny chunks
            chunk_size = 3
            for i in range(0, len(full_response), chunk_size):
                sock.send(full_response[i:i+chunk_size])
                time.sleep(0.01) # Small delay to force multiple recv

        self.server.behavior = handle_split_send
        
        files = self.client.list_files()
        self.assertEqual(files, ["partial"])

    def test_idempotency_request_id_reuse(self):
        """Test client reuses Request ID on retry."""
        print("DEBUG: Running test_idempotency_request_id_reuse")
        attempt_ids = []
        
        def handle_timeout_first(sock, header, payload):
            attempt_ids.append(header.request_id)
            if len(attempt_ids) == 1:
                # Simulate timeout (don't send response)
                return
            else:
                # Second attempt: send response
                resp_payload = json.dumps(["retry_success"]).encode("utf-8")
                response = encode_message(OP_LIST, 0, header.request_id, resp_payload)
                sock.sendall(response)

        self.server.behavior = handle_timeout_first
        
        files = self.client.list_files()
        self.assertEqual(files, ["retry_success"])
        
        # Verify 2 attempts
        self.assertEqual(len(attempt_ids), 2)
        # Verify IDs match (Idempotency)
        self.assertEqual(attempt_ids[0], attempt_ids[1])

if __name__ == '__main__':
    unittest.main()
