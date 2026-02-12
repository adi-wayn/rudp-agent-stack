"""
TCP Client Transport.
Standard TCP socket wrapper for comparison/baseline.
"""
import socket

class TCPClientSocket:
    """
    TCP Client Socket wrapper.
    """
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self, address: tuple):
        # TODO: Implement connect
        self.sock.connect(address)

    def send(self, data: bytes):
        # TODO: Implement send
        self.sock.sendall(data)

    def recv(self, bufsize: int) -> bytes:
        # TODO: Implement recv
        return self.sock.recv(bufsize)

    def close(self):
        # TODO: Implement close
        self.sock.close()
