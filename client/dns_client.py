import json
import logging
import threading
from typing import Optional
from client.transport.rudp_client import RUDPClientTransport
from common.http_packet import HTTPBuilder

logger = logging.getLogger(__name__)

class DNSClient:
    """
    Client for the Custom DNS protocol.
    Resolves domains using DNS over HTTP (DoH) layered strictly over the custom Reliable UDP (RUDP) Transport.
    """
    def __init__(self, dns_server_ip: str, client_ip: str = "NOT_SET", port: int = 8053):
        self.dns_server_ip = dns_server_ip
        self.client_ip = client_ip
        self.port = port

    def resolve(self, hostname: str) -> Optional[str]:
        """
        Resolve a hostname to an IP address by communicating with the DoHRUDPServer.
        Uses threading.Event to synchronously wait for the asynchronous RUDP response.
        """
        transport = None
        response_event = threading.Event()
        resolved_ip = None
        
        # Buffer to hold asynchronous response
        response_buffer = []

        def handle_response(data: bytes):
            response_buffer.append(data)
            response_event.set()

        try:
            # Enforce Layer 4 Binding for Virtual IP Routing
            transport = RUDPClientTransport(
                server_host=self.dns_server_ip, 
                server_port=self.port, 
                client_ip=self.client_ip
            )
            transport.set_message_handler(handle_response)
            
            # Start background async receive loop
            transport.start()
            
            # Format raw HTTP GET Request
            request_str = HTTPBuilder.build_doh_request(hostname, self.dns_server_ip, self.port)
            
            # Send serialized text over RUDP using arbitrary request_id=1 for multiplexer compat
            logger.info(f"Sending DoH request for '{hostname}' to {self.dns_server_ip}:{self.port} via RUDP")
            transport.send(request_str.encode('utf-8'), request_id=1)
            
            # Synchronously await the payload (timeout 5s)
            if response_event.wait(timeout=5.0):
                payload = response_buffer[0].decode('utf-8')
                
                data = HTTPBuilder.parse_response(payload)
                if data:
                    if data.get("status") == 200:
                        resolved_ip = data.get("data", {}).get("ip")
                    else:
                        logger.error(f"DNS Server returned error: {data}")
                else:
                    logger.error("Failed to parse HTTP/JSON DoH response from RUDP payload")
            else:
                logger.error("DoH request timed out")
                
        except Exception as e:
            logger.error(f"Failed to perform DNS resolution: {e}")
        finally:
            if transport:
                transport.close()
                
        return resolved_ip
