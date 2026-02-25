import unittest
import json
import time
from server.dns.dns_cache import DNSCache
from server.dns_server import DoHRUDPServer

class TestDNSCache(unittest.TestCase):
    def test_seed_record(self):
        cache = DNSCache()
        self.assertEqual(cache.get("agent.local"), "127.0.0.1")
        self.assertIsNone(cache.get("unknown.local"))
        
    def test_ttl_expiration(self):
        cache = DNSCache()
        cache.set("test.local", "192.168.1.1", ttl=0.1)
        self.assertEqual(cache.get("test.local"), "192.168.1.1")
        time.sleep(0.15)
        self.assertIsNone(cache.get("test.local"))

class MockRUDPTransport:
    def __init__(self):
        self.sent_data = None
        self.sent_addr = None
        
    def set_message_handler(self, handler):
        self.handler = handler
        
    def send(self, data: bytes, request_id: int, client_addr: tuple):
        self.sent_data = data
        self.sent_addr = client_addr
        
    def start(self):
        pass

class TestDoHRUDPServer(unittest.TestCase):
    def test_valid_dns_query(self):
        server = DoHRUDPServer()
        mock_transport = MockRUDPTransport()
        server.transport = mock_transport
        mock_transport.set_message_handler(server.handle_message)
        
        # Craft DoH request
        req = "GET /dns-query?name=agent.local HTTP/1.1\r\nHost: 127.0.0.1:8053\r\n\r\n"
        
        # Simulate receiving packet
        server.handle_message(req.encode('utf-8'), ("127.0.0.1", 12345))
        
        self.assertIsNotNone(mock_transport.sent_data)
        self.assertEqual(mock_transport.sent_addr, ("127.0.0.1", 12345))
        
        resp = mock_transport.sent_data.decode('utf-8')
        self.assertTrue(resp.startswith("HTTP/1.1 200 OK"))
        
        # Extract JSON body
        body = resp.split('\r\n\r\n')[1]
        data = json.loads(body)
        
        self.assertEqual(data["status"], 200)
        self.assertEqual(data["data"]["ip"], "127.0.0.1")

    def test_invalid_dns_query(self):
        server = DoHRUDPServer()
        mock_transport = MockRUDPTransport()
        server.transport = mock_transport
        mock_transport.set_message_handler(server.handle_message)
        
        # Craft DoH request for missing record
        req = "GET /dns-query?name=missing.local HTTP/1.1\r\nHost: 127.0.0.1:8053\r\n\r\n"
        
        # Simulate receiving packet
        server.handle_message(req.encode('utf-8'), ("127.0.0.1", 12345))
        
        self.assertIsNotNone(mock_transport.sent_data)
        
        resp = mock_transport.sent_data.decode('utf-8')
        self.assertTrue(resp.startswith("HTTP/1.1 404 Not Found"))
        
        body = resp.split('\r\n\r\n')[1]
        data = json.loads(body)
        
        self.assertEqual(data["status"], 404)
        self.assertEqual(data["error"], "Not Found")

if __name__ == '__main__':
    unittest.main()
