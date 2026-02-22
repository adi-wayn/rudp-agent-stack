import unittest
import socket
import threading
import time
from server.transport.rudp_adapter import RUDPServerAdapter
from common.app_envelope import encode_message, decode_header, HEADER_SIZE

class TestRUDPServerAdapter(unittest.TestCase):
    def setUp(self):
        self.port = 9090 # Use a different port for testing
        self.adapter = RUDPServerAdapter(port=self.port)
        self.received_messages = []
        self.lock = threading.Lock()

    def mock_on_message(self, client_id, data):
        with self.lock:
            self.received_messages.append((client_id, data))
        
        # Simple Echo response
        header = decode_header(data[:HEADER_SIZE])
        return encode_message(header.opcode, header.request_id, b"PONG")

    def test_single_client_roundtrip(self):
        """
        Test a full roundtrip with a single UDP client.
        """
        # Start adapter in a background thread
        print(f"[TEST] Starting server on {self.port}")
        server_thread = threading.Thread(target=self.adapter.serve, args=(self.mock_on_message,), daemon=True)
        server_thread.start()
        time.sleep(0.5) # Wait for bind

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = b"PING"
        ping_msg = encode_message(0xFF, 123, payload)
        
        print(f"[TEST] Sending {len(ping_msg)} bytes to 127.0.0.1:{self.port}")
        client_sock.sendto(ping_msg, ("127.0.0.1", self.port))
        client_sock.settimeout(3.0)
        
        try:
            print("[TEST] Waiting for response...")
            resp_data, addr = client_sock.recvfrom(1024)
            print(f"[TEST] Received {len(resp_data)} bytes from {addr}")
            header = decode_header(resp_data[:HEADER_SIZE])
            self.assertEqual(header.request_id, 123)
            self.assertEqual(resp_data[HEADER_SIZE:], b"PONG")
        except socket.timeout:
            print("[TEST] Client timed out waiting for response")
            self.fail("Client timed out waiting for response")
        finally:
            self.adapter.close()
            client_sock.close()

    def test_multi_client_isolation(self):
        """
        Verify that multiple clients are handled correctly without state collision.
        """
        server_thread = threading.Thread(target=self.adapter.serve, args=(self.mock_on_message,), daemon=True)
        server_thread.start()
        time.sleep(0.1)

        client1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        msg1 = encode_message(0x01, 1, b"Client1")
        msg2 = encode_message(0x01, 2, b"Client2")
        
        client1.sendto(msg1, ("127.0.0.1", self.port))
        client2.sendto(msg2, ("127.0.0.1", self.port))
        
        client1.settimeout(1.0)
        client2.settimeout(1.0)
        
        resp1, _ = client1.recvfrom(1024)
        resp2, _ = client2.recvfrom(1024)
        
        self.assertEqual(resp1[HEADER_SIZE:], b"PONG")
        self.assertEqual(resp2[HEADER_SIZE:], b"PONG")
        
        with self.lock:
            self.assertEqual(len(self.received_messages), 2)
            # Ensure client IDs are different (different source ports)
            self.assertNotEqual(self.received_messages[0][0], self.received_messages[1][0])

        self.adapter.close()
        client1.close()
        client2.close()

    def test_partial_envelope_reassembly(self):
        """
        Test that messages are only delivered after full reassembly.
        """
        server_thread = threading.Thread(target=self.adapter.serve, args=(self.mock_on_message,), daemon=True)
        server_thread.start()
        time.sleep(0.1)

        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = b"LONG_TEST_PAYLOAD"
        full_msg = encode_message(0x01, 999, payload)
        
        # Send only the header first
        client.sendto(full_msg[:HEADER_SIZE], ("127.0.0.1", self.port))
        time.sleep(0.1)
        
        with self.lock:
            self.assertEqual(len(self.received_messages), 0, "Message should NOT be delivered yet")
            
        # Send half of the payload
        mid = HEADER_SIZE + (len(payload) // 2)
        client.sendto(full_msg[HEADER_SIZE:mid], ("127.0.0.1", self.port))
        time.sleep(0.1)

        with self.lock:
            self.assertEqual(len(self.received_messages), 0, "Message should NOT be delivered yet")

        # Send the rest
        client.sendto(full_msg[mid:], ("127.0.0.1", self.port))
        time.sleep(0.1)

        with self.lock:
            self.assertEqual(len(self.received_messages), 1, "Message SHOULD be delivered now")
            self.assertEqual(self.received_messages[0][1], full_msg)

        self.adapter.close()
        client.close()

    def test_clean_shutdown(self):
        """
        Verify that the adapter stops gracefully.
        """
        server_thread = threading.Thread(target=self.adapter.serve, args=(self.mock_on_message,), daemon=True)
        server_thread.start()
        time.sleep(0.1)
        self.assertTrue(self.adapter.running)
        
        self.adapter.close()
        time.sleep(1.2) # Wait for timeout loop to exit
        self.assertFalse(self.adapter.running)
        self.assertIsNone(self.adapter.sock)

if __name__ == "__main__":
    unittest.main()
