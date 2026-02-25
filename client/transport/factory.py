"""
Transport Factory.
Centralizes creation of Transport instances (TCP/RUDP).
"""
from client.transport.tcp_client import TCPClient
from client.transport.rudp_client import RUDPClientTransport
import logging
class TransportFactory:
    """
    Factory for creating transport clients.
    """
    @staticmethod
    def create(mode: str, server_ip: str, server_port: int, client_ip: str = "NOT_SET", **kwargs):
        """
        Create a transport instance based on mode.
        """
        if mode.lower() == 'tcp':
            BASIC_LOG_FORMAT = "[TCP-Client] %(asctime)s - %(levelname)s - %(message)s"
            logging.basicConfig(level=logging.INFO, format=BASIC_LOG_FORMAT)
            return TCPClient(server_ip, server_port, client_ip=client_ip)
            
        elif mode.lower() == 'rudp':
            # RUDP wrapper or socket
            BASIC_LOG_FORMAT = "[RUDP-Client] %(asctime)s - %(levelname)s - %(message)s"
            logging.basicConfig(level=logging.INFO, format=BASIC_LOG_FORMAT)
            return RUDPClientTransport(server_ip, server_port, client_ip=client_ip, failure_engine=kwargs.get("failure_engine"))
        else:
            raise ValueError(f"Unknown transport mode: {mode}")
