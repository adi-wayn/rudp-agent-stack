"""
TCP Server Transport.
"""
import socket

class TCPServerSocket:
    """
    TCP Server Wrapper.
    """
    def __init__(self, port: int):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(('0.0.0.0', port))

    def listen(self):
        self.sock.listen()

    def accept(self):
        return self.sock.accept()
