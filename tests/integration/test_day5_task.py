
import unittest
import threading
import socket
import json
import logging
import time
import struct
from typing import Optional, Tuple

from client.agent_client import AgentClient, ClientRequestSpec
from common.constants import (
    OP_TASK_SEARCH_REPORT, OP_TASK_FILTER_LINES, OP_GET,
    PROTOCOL_VERSION, HEADER_SIZE, OP_TASK_HASH_AND_STORE
)
from common.app_envelope import decode_header, encode_message
from server.agent_server import AgentServer # Indirectly used if needed, but we mock

# Configure logging for tests
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("TestDay5Task")

class ThreadedMockServer:
    """
    A simple single-threaded TCP mock server that understands 
    the Agent Protocol Envelope and can be programmed with interactions.
    """
    def __init__(self, port=0):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", port))
        self.port = self._sock.getsockname()[1]
        self._running = False
        self._thread = None
        self.interactions = [] # List of (expected_opcode, response_dict_or_bytes)
        self.received_requests = []
    
    def start(self):
        self._running = True
        self._sock.listen(1)
        self._thread = threading.Thread(target=self._accept_loop)
        self._thread.daemon = True
        self._thread.start()
        
    def stop(self):
        self._running = False
        if self._sock:
            self._sock.close()
            
    def expect(self, opcode: int, response: dict | bytes, status=200):
        self.interactions.append({
            "expect_opcode": opcode,
            "response": response,
            "status": status
        })

    def _accept_loop(self):
        try:
            while self._running:
                try:
                    self._sock.settimeout(1.0)
                    conn, addr = self._sock.accept()
                    self._handle_conn(conn)
                except socket.timeout:
                    continue
                except OSError:
                    break
        except Exception as e:
            logger.error(f"Mock Server Accept Error: {e}")

    def _handle_conn(self, conn):
        try:
            while self._running:
                # 1. Read Header
                header_data = conn.recv(HEADER_SIZE)
                if not header_data:
                    break
                
                header = decode_header(header_data)
                
                # 2. Read Payload
                payload_data = b""
                while len(payload_data) < header.payload_len:
                    chunk = conn.recv(header.payload_len - len(payload_data))
                    if not chunk:
                        break
                    payload_data += chunk
                
                # Record Request
                req_json = {}
                try:
                    req_json = json.loads(payload_data.decode("utf-8"))
                except:
                    pass
                
                self.received_requests.append({
                    "opcode": header.opcode,
                    "request_id": header.request_id,
                    "payload": req_json
                })

                # Find Next Interaction
                if not self.interactions:
                    # Default: OK
                    resp = b'{}'
                    self._send_response(conn, header.opcode, header.request_id, 200, resp)
                    continue

                interaction = self.interactions.pop(0)
                if interaction["expect_opcode"] != header.opcode:
                    logger.error(f"Mock Expectation Mismatch! Expected {interaction['expect_opcode']}, got {header.opcode}")
                    # Send Error?
                    self._send_response(conn, header.opcode, header.request_id, 500, b'{"message": "Mock Mismatch"}')
                else:
                    # Valid
                    resp_data = interaction["response"]
                    if isinstance(resp_data, dict):
                        # Inject status if missing
                        if "status" not in resp_data:
                             resp_data["status"] = interaction["status"]
                        resp_bytes = json.dumps(resp_data).encode("utf-8")
                    else:
                         # Raw bytes (already packed for Mixed Mode if needed)
                         resp_bytes = resp_data
                    
                    self._send_response(conn, header.opcode, header.request_id, 0, resp_bytes)

        except Exception as e:
            logger.error(f"Mock Connection Error: {e}")
        finally:
            conn.close()

    def _send_response(self, conn, opcode, req_id, _, payload_bytes):
        # We ignore flags/status in arg for now, assume payload contains everything needed 
        # (Since generic ResponseBuilder isn't used here, we build raw)
        # Note: Server logic usually puts status inside JSON.
        
        # Build Envelope
        msg = encode_message(opcode, 0, req_id, payload_bytes)
        conn.sendall(msg)


class TestDay5Client(unittest.TestCase):
    
    def setUp(self):
        self.server = ThreadedMockServer()
        self.server.start()
        # Mock Transport by pointing to Mock Server Port
        from client.transport.tcp_client import TCPClient
        self.transport = TCPClient(host="127.0.0.1", port=self.server.port)
        self.client = AgentClient(transport=self.transport)

    def tearDown(self):
        self.client.close()
        self.server.stop()

    def test_task_inline_result(self):
        """
        Verify OP_TASK_SEARCH_REPORT returns inline result.
        """
        # Mock: Expect TASK -> Return Result
        self.server.expect(
            OP_TASK_SEARCH_REPORT,
            {"status": 200, "result": "Found 5 matches in 2 files"},
            status=200
        )
        
        # Execute
        res = self.client.execute(
            OP_TASK_SEARCH_REPORT, 
            task_type="SEARCH_REPORT", 
            query="test"
        )
        
        # Verify
        self.assertEqual(res.status, 200)
        self.assertEqual(res.data.get("result"), "Found 5 matches in 2 files")
        
        # Verify Request on Server
        req = self.server.received_requests[0]
        self.assertEqual(req["opcode"], OP_TASK_SEARCH_REPORT)
        self.assertEqual(req["payload"]["query"], "test")

    def test_task_artifact_flow(self):
        """
        Verify OP_TASK_FILTER_LINES triggers automatic OP_GET for artifact.
        """
        artifact_name = "filtered_output.txt"
        file_content = b"Line 1\nLine 2\n"
        
        # 1. Expect TASK -> Return Artifact Reference
        self.server.expect(
            OP_TASK_FILTER_LINES,
            {"status": 200, "artifact_file": artifact_name},
            status=200
        )
        
        # 2. Expect GET -> Return File Content
        # We need to construct a Mixed Mode Response for GET
        # Format: 4 bytes meta_len + JSON_Meta + Binary
        meta = {"status": 200, "filename": artifact_name}
        meta_bytes = json.dumps(meta).encode("utf-8")
        meta_len = len(meta_bytes)
        
        # Mixed Mode Prefix: 4 bytes big endian length
        mixed_payload = struct.pack("!I", meta_len) + meta_bytes + file_content
        
        self.server.expect(
            OP_GET,
            mixed_payload,
            status=200
        )

        # Execute
        res = self.client.execute(
            OP_TASK_FILTER_LINES,
            task_type="FILTER_LINES",
            input_file="log.txt",
            pattern="Line"
        )

        # Verify
        self.assertEqual(res.status, 200)
        self.assertIn("Task Complete", res.data["status"])
        self.assertIn("artifact_local_path", res.data)
        
        # Verify File Saved
        saved_path = res.data["artifact_local_path"]
        with open(saved_path, "rb") as f:
            content = f.read()
            self.assertEqual(content, file_content)

        # Verify Requests
        self.assertEqual(len(self.server.received_requests), 2)
        task_req = self.server.received_requests[0]
        get_req = self.server.received_requests[1]
        
        self.assertEqual(task_req["opcode"], OP_TASK_FILTER_LINES)
        self.assertEqual(get_req["opcode"], OP_GET)
        self.assertEqual(get_req["payload"]["filename"], artifact_name)
        
    def test_task_error(self):
        """
        Verify Error propagation.
        """
        self.server.expect(
            OP_TASK_HASH_AND_STORE,
            {"status": 500, "message": "Internal Error"},
            status=500
        )
        
        res = self.client.execute(OP_TASK_HASH_AND_STORE, task_type="HASH")
        
        self.assertEqual(res.status, 500)
        self.assertIn("Internal Error", res.error)

if __name__ == "__main__":
    unittest.main()
