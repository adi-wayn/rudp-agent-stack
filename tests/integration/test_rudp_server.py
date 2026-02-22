import unittest
import socket
import threading
import time
from server.transport.rudp_server import RUDPServerTransport
from common.app_envelope import encode_message, decode_header, HEADER_SIZE

class TestRUDPServerTransport(unittest.TestCase):
    def setUp(self):
        self.port = 9091 # Different port for transport test
        self.transport = RUDPServerTransport(port=self.port)
        self.received_messages = []
        self.lock = threading.Lock()

    def mock_on_message(self, client_id, data):
        with self.lock:
            self.received_messages.append((client_id, data))
        
        # Simple Echo response (PONG)
        header = decode_header(data[:HEADER_SIZE])
        return encode_message(header.opcode, header.request_id, b"PONG")

    def test_single_client_roundtrip(self):
        """
        Test a full roundtrip with a single UDP client.
        """
        # Start transport in background thread
        server_thread = threading.Thread(target=self.transport.serve, args=(self.mock_on_message,), daemon=True)
        server_thread.start()
        time.sleep(0.5) # Wait for bind

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = b"PING"
        ping_msg = encode_message(0xFF, 124, payload)
        
        client_sock.sendto(ping_msg, ("127.0.0.1", self.port))
        client_sock.settimeout(2.0)
        
        try:
            resp_data, addr = client_sock.recvfrom(1024)
            header = decode_header(resp_data[:HEADER_SIZE])
            self.assertEqual(header.request_id, 124)
            self.assertEqual(resp_data[HEADER_SIZE:], b"PONG")
        finally:
            self.transport.close()
            client_sock.close()

    def test_multi_client_isolation(self):
        """
        Verify that multiple clients are handled correctly without state collision.
        """
        server_thread = threading.Thread(target=self.transport.serve, args=(self.mock_on_message,), daemon=True)
        server_thread.start()
        time.sleep(0.5)

        client1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        msg1 = encode_message(0x01, 1, b"Alpha")
        msg2 = encode_message(0x01, 2, b"Beta")
        
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

        self.transport.close()
        client1.close()
        client2.close()

    def test_partial_envelope_reassembly(self):
        """
        Test that messages are only delivered after full reassembly.
        """
        server_thread = threading.Thread(target=self.transport.serve, args=(self.mock_on_message,), daemon=True)
        server_thread.start()
        time.sleep(0.5)

        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = b"SEGMENTED_PAYLOAD"
        full_msg = encode_message(0x01, 777, payload)
        
        # Send byte by byte (aggressive segmentation)
        for i in range(len(full_msg)):
            client.sendto(full_msg[i:i+1], ("127.0.0.1", self.port))
            time.sleep(0.01)
        
        # Wait a bit longer for all fragments to be processed
        time.sleep(0.2)
        
        with self.lock:
            self.assertEqual(len(self.received_messages), 1, "Message SHOULD be delivered now")
            self.assertEqual(self.received_messages[0][1], full_msg)

        self.transport.close()
        client.close()

if __name__ == "__main__":
    unittest.main()
