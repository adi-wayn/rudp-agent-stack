import unittest
import threading
from unittest.mock import patch, MagicMock
from client.dns_client import DNSClient

class TestDNSClient(unittest.TestCase):
    
    @patch('client.dns_client.RUDPClientTransport')
    def test_doh_resolve_success(self, mock_transport_class):
        # Mock the transport instance
        mock_transport = MagicMock()
        mock_transport_class.return_value = mock_transport
        
        # We need to simulate the asynchronous callback from the transport layer
        def side_effect_start():
            # Trigger the attached callback manually with a mock valid HTTP JSON payload
            valid_http_response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: application/json\r\n"
                b"\r\n"
                b'{"status": 200, "data": {"ip": "127.0.0.1", "ttl": 300}}'
            )
            
            # The client binds a handler anonymously; we need to extract it from set_message_handler
            # Alternatively we extract it from the mock calls
            handler = mock_transport.set_message_handler.call_args[0][0]
            # Emit the payload in a new thread to mimic real async RUDP transport behavior
            threading.Thread(target=handler, args=(valid_http_response,)).start()
            
        mock_transport.start.side_effect = side_effect_start
        
        # Test Execution
        client = DNSClient("127.0.0.1", port=8053)
        resolved_ip = client.resolve("agent.local")
        
        # Assertions
        self.assertEqual(resolved_ip, "127.0.0.1")
        mock_transport.send.assert_called_once()
        sent_data = mock_transport.send.call_args[0][0].decode('utf-8')
        
        self.assertIn("GET /dns-query?name=agent.local HTTP/1.1", sent_data)
        self.assertIn("Host: 127.0.0.1:8053", sent_data)

    @patch('client.dns_client.RUDPClientTransport')
    def test_doh_resolve_404_not_found(self, mock_transport_class):
        mock_transport = MagicMock()
        mock_transport_class.return_value = mock_transport
        
        def side_effect_start():
            invalid_http_response = (
                b"HTTP/1.1 404 Not Found\r\n"
                b"Content-Type: application/json\r\n"
                b"\r\n"
                b'{"status": 404, "error": "Not Found"}'
            )
            handler = mock_transport.set_message_handler.call_args[0][0]
            threading.Thread(target=handler, args=(invalid_http_response,)).start()
            
        mock_transport.start.side_effect = side_effect_start
        
        client = DNSClient("127.0.0.1", port=8053)
        resolved_ip = client.resolve("missing.local")
        
        self.assertIsNone(resolved_ip)

if __name__ == '__main__':
    unittest.main()
