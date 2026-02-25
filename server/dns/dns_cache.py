import time
import threading
from typing import Dict, Tuple, Optional

class DNSCache:
    """
    Thread-safe DNS Cache for mapping domain names to virtual IPs.
    Supports TTL expiration mapping.
    """
    def __init__(self):
        self._lock = threading.Lock()
        # Mapping: domain -> (ip, expires_at)
        self._cache: Dict[str, Tuple[str, float]] = {}
        
        # Seed default Agent record
        self.set("agent.local", "127.0.0.1", ttl=300)

    def set(self, name: str, ip: str, ttl: int = 300) -> None:
        with self._lock:
            self._cache[name] = (ip, time.time() + ttl)

    def get(self, name: str) -> Optional[str]:
        with self._lock:
            if name in self._cache:
                ip, expires_at = self._cache[name]
                if time.time() > expires_at:
                    # TTL expired
                    del self._cache[name]
                    return None
                return ip
            return None
