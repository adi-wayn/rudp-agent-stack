"""
Idempotency Cache.
Ensures that duplicate requests (same client_id + request_id) return cached responses
instead of re-executing non-idempotent operations.
"""
import time
import logging
from dataclasses import dataclass
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# TTL for idempotency records in seconds (Spec: 120s)
IDEMPOTENCY_TTL = 120.0

@dataclass
class CachedResponse:
    response_data: bytes
    timestamp: float

class IdempotencyCache:
    """
    Stores responses keyed by (client_id, request_id, opcode).
    Implements TTL-based cleanup.
    """
    def __init__(self):
        # Key: (client_id, request_id, opcode) -> CachedResponse
        self._cache: Dict[Tuple[str, int, int], CachedResponse] = {}

    def get_response(self, client_id: str, request_id: int, opcode: int) -> Optional[bytes]:
        """
        Retrieve a cached response if it exists and hasn't expired.
        """
        key = (client_id, request_id, opcode)
        entry = self._cache.get(key)
        
        if entry:
            if time.time() - entry.timestamp < IDEMPOTENCY_TTL:
                logger.info(f"Idempotency HIT for {key}")
                return entry.response_data
            else:
                # Expired
                del self._cache[key]
        
        return None

    def store_response(self, client_id: str, request_id: int, opcode: int, response_data: bytes):
        """
        Cache a response.
        """
        key = (client_id, request_id, opcode)
        self._cache[key] = CachedResponse(
            response_data=response_data,
            timestamp=time.time()
        )
        logger.debug(f"Stored response for {key}, TTL={IDEMPOTENCY_TTL}s")

    def cleanup(self):
        """
        Remove expired entries. 
        Should be called periodically by the server loop.
        """
        now = time.time()
        keys_to_delete = [
            k for k, v in self._cache.items()
            if now - v.timestamp >= IDEMPOTENCY_TTL
        ]
        for k in keys_to_delete:
            del self._cache[k]
        
        if keys_to_delete:
            logger.debug(f"Cleaned up {len(keys_to_delete)} expired idempotency records")
