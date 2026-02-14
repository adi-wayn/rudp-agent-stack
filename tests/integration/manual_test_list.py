"""
Manual Test Client for LIST operation.
"""
import socket
import sys
import os
import json
import struct

sys.path.append(os.getcwd())

from common.app_envelope import encode_message, decode_header, HEADER_SIZE
from common.constants import OP_LIST, LOOPBACK_IP, AGENT_SERVER_PORT

def test_list():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((LOOPBACK_IP, AGENT_SERVER_PORT))
        print(f"Connected to {LOOPBACK_IP}:{AGENT_SERVER_PORT}")
        
        # Send LIST request
        req_id = 123
        msg = encode_message(OP_LIST, 0, req_id, b'')
        sock.sendall(msg)
        print("Sent LIST request")
        
        # Receive Response
        # Header
        header_data = sock.recv(HEADER_SIZE)
        if not header_data:
            print("No response")
            return
            
        header = decode_header(header_data)
        print(f"Received Header: Op={header.opcode} Len={header.payload_len}")
        
        # Payload
        payload = sock.recv(header.payload_len)
        print(f"Raw Payload: {payload}")
        
        files = json.loads(payload.decode("utf-8"))
        print(f"Files in sandbox: {files}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    test_list()
