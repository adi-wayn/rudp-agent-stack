import json
import logging
from typing import Tuple
from common.constants import LOOPBACK_IP
from common.http_packet import HTTPBuilder
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
            
        name = HTTPBuilder.parse_request(http_request)
        if name:
            logger.info(f"DoH Query for '{name}' from {client_addr}")
            
            # Query our cache
            ip = self.cache.get(name)
            
            if ip:
                # 200 OK
                logger.info(f"DoH Query for '{name}' successfully resolved to {ip} from cache for {client_addr}")
                response = HTTPBuilder.build_json_response(200, {
                    "status": 200,
                    "data": {
                        "ip": ip,
                        "ttl": 300
                    }
                })
            else:
                # 404 Not Found
                logger.warning(f"DoH Query for '{name}' from {client_addr} not found in cache (404)")
                response = HTTPBuilder.build_json_response(404, {"status": 404, "error": "Not Found"})
            
            # Provide request_id=0 as RUDP client multiplexing does not use it at the L4 abstraction level
            logger.info(f"Dispatched DoH response back to {client_addr}")
            self.transport.send(response.encode('utf-8'), request_id=0, client_addr=client_addr)

    def start(self):
        """
        Starts the DoH Server event loop blockingly.
        """
        logger.info(f"Starting DoHRUDPServer on port {self.port}")
        self.transport.start()
