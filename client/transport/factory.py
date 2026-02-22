"""
Transport Factory.
Centralizes creation of Transport instances (TCP/RUDP).
"""
from client.transport.tcp_client import TCPClient
from client.transport.rudp_client import RUDPClientTransport

class TransportFactory:
    """
    Factory for creating transport clients.
    """
    @staticmethod
    def create(mode: str, server_ip: str, server_port: int, **kwargs):
        """
        Create a transport instance based on mode.
        """
        if mode.lower() == 'tcp':
            return TCPClient(server_ip, server_port)
        elif mode.lower() == 'rudp':
            # RUDP wrapper or socket
            return RUDPClientTransport(server_ip, server_port)
        else:
            raise ValueError(f"Unknown transport mode: {mode}")
