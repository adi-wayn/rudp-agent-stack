import time
import json
import threading
import unittest

from server.dns_server import DoHRUDPServer
from client.transport.rudp_client import RUDPClientTransport

class TestDoHOverRUDPIntegration(unittest.TestCase):
    def setUp(self):
        # Start DoHRUDPServer on a specific test port to avoid conflicts
        self.server_port = 18053
        self.server = DoHRUDPServer(port=self.server_port)
        self.server_thread = threading.Thread(target=self.server.start, daemon=True)
        self.server_thread.start()
        
        # Give server time to bind
        time.sleep(0.5)
        
        # Initialize RUDP Client connected to the server
        self.client = RUDPClientTransport(server_host="127.0.0.1", server_port=self.server_port)
        self.response_data = None
        self.response_event = threading.Event()
        
        def handle_response(data: bytes):
            self.response_data = data
            self.response_event.set()
            
        self.client.set_message_handler(handle_response)
        
        # Start client tick loop
        self.client_thread = threading.Thread(target=self.client.start, daemon=True)
        self.client_thread.start()
        
    def tearDown(self):
        self.client.close()
        self.server.transport.close()
        # Wait for threads to avoid leaking open sockets between tests
        time.sleep(0.2)
        
    def test_doh_over_rudp_success(self):
        # Craft raw HTTP DoH request
        req = "GET /dns-query?name=agent.local HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n"
        
        # Send raw request over RUDP
        # Note: request_id is not strictly used by DoHRUDPServer, but we pass 1.
        self.client.send(req.encode('utf-8'), request_id=1)
        
        # Wait for response with timeout
        self.assertTrue(self.response_event.wait(timeout=5.0), "Timeout waiting for DoH response over RUDP")
        
        resp = self.response_data.decode('utf-8')
        self.assertTrue(resp.startswith("HTTP/1.1 200 OK"))
        
        body = resp.split('\r\n\r\n')[1]
        data = json.loads(body)
        
        self.assertEqual(data["status"], 200)
        self.assertEqual(data["data"]["ip"], "127.0.0.1")
        self.assertEqual(data["data"]["ttl"], 300)

if __name__ == '__main__':
    unittest.main()
