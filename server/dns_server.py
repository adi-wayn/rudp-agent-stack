import json
import logging
from typing import Tuple
from common.constants import LOOPBACK_IP
from server.transport.rudp_server import RUDPServerTransport
from server.dns.dns_cache import DNSCache

logger = logging.getLogger("DNSServer")

class DoHRUDPServer:
    """
    DNS over HTTP (DoH) Server, running exclusively on the custom RUDP Transport.
    Listens for HTTP GET requests packaged inside RUDP datagrams payloads.
    """
    def __init__(self, port: int = 8053):
        self.cache = DNSCache()
        self.port = port
        # DNS Server uses the same physical 127.0.0.1 loopback, separating traffic by port
        self.transport = RUDPServerTransport(port=self.port, bind_ip=LOOPBACK_IP)
        self.transport.set_message_handler(self.handle_message)

    def handle_message(self, data: bytes, client_addr: Tuple[str, int]) -> None:
        """
        Callback triggered by the RUDPServerTransport when a complete, ordered payload is ready.
        Parses as a raw HTTP GET request string over custom transport.
        """
        try:
            http_request = data.decode('utf-8')
        except UnicodeDecodeError:
            logger.warning(f"Received non-UTF-8 payload from {client_addr}")
            return
            
        lines = http_request.split('\r\n')
        if not lines:
            return
            
        # Example Request Line: GET /dns-query?name=agent.local HTTP/1.1
        request_line = lines[0]
        parts = request_line.split(' ')
        if len(parts) >= 2 and parts[0] == 'GET':
            url = parts[1]
            if url.startswith('/dns-query?name='):
                name = url.split('=')[1].split(' ')[0] # Ensure we don't catch protocol trailing string if there's no space formatting edge-cases
                logger.info(f"DoH Query for '{name}' from {client_addr}")
                
                # Query our cache
                ip = self.cache.get(name)
                
                if ip:
                    # 200 OK
                    response_body = json.dumps({
                        "status": 200,
                        "data": {
                            "ip": ip,
                            "ttl": 300
                        }
                    })
                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: application/json\r\n"
                        f"Content-Length: {len(response_body)}\r\n"
                        "\r\n"
                        f"{response_body}"
                    )
                else:
                    # 404 Not Found
                    response_body = json.dumps({"status": 404, "error": "Not Found"})
                    response = (
                        "HTTP/1.1 404 Not Found\r\n"
                        "Content-Type: application/json\r\n"
                        f"Content-Length: {len(response_body)}\r\n"
                        "\r\n"
                        f"{response_body}"
                    )
                
                # Provide request_id=0 as RUDP client multiplexing does not use it at the L4 abstraction level
                self.transport.send(response.encode('utf-8'), request_id=0, client_addr=client_addr)

    def start(self):
        """
        Starts the DoH Server event loop blockingly.
        """
        logger.info(f"Starting DoHRUDPServer on port {self.port}")
        self.transport.start()
