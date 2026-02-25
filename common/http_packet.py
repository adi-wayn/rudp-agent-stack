import json
from typing import Optional, Dict, Any

class HTTPBuilder:
    """
    Utility class for building and parsing simple HTTP messages.
    Used for DNS over HTTP (DoH) communication over custom RUDP transport.
    """
    
    @staticmethod
    def build_doh_request(domain_name: str, host: str, port: int) -> str:
        """Constructs a raw HTTP GET request string for DoH."""
        return (
            f"GET /dns-query?name={domain_name} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Accept: application/json\r\n\r\n"
        )
        
    @staticmethod
    def parse_request(raw_data: str) -> Optional[str]:
        """Parses a raw HTTP request string and extracts the DoH domain name."""
        lines = raw_data.split('\r\n')
        if not lines:
            return None
            
        request_line = lines[0]
        parts = request_line.split(' ')
        if len(parts) >= 2 and parts[0] == 'GET':
            url = parts[1]
            if url.startswith('/dns-query?name='):
                name = url.split('=')[1].split(' ')[0]
                return name
        return None
        
    @staticmethod
    def build_json_response(status_code: int, data: Dict[str, Any]) -> str:
        """Constructs a raw HTTP response string with a JSON body."""
        body_str = json.dumps(data)
        
        # Simple status text mapping
        status_text = "OK"
        if status_code == 404:
            status_text = "Not Found"
        elif status_code != 200:
            status_text = "Error"
            
        return (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body_str)}\r\n"
            "\r\n"
            f"{body_str}"
        )
        
    @staticmethod
    def parse_response(raw_data: str) -> Optional[Dict[str, Any]]:
        """Parses a raw HTTP response string and returns the extracted JSON dictionary."""
        if "\r\n\r\n" in raw_data:
            body = raw_data.split("\r\n\r\n", 1)[1]
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return None
        return None
