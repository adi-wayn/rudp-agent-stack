import socket
import logging

logging.basicConfig(level=logging.INFO)
try:
    s = socket.create_connection(("127.0.0.1", 8080), timeout=2.0)
    print("Connected to server successfully.")
    s.close()
except Exception as e:
    print(f"Failed to connect: {e}")
