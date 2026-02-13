"""
Agent Server Module.
Main entry point for the Agent-based Application Server.
Orchestrates the request processing pipeline.
"""
import logging
from typing import Tuple

from common.app_envelope import decode_header, encode_message
from common.errors import ErrorCode

from server.agent.validations import PolicyGuard
from server.agent.idempotency import IdempotencyCache
from server.agent.dispatcher import Dispatcher

logger = logging.getLogger(__name__)

class AgentServer:
    """
    Agent Server Application Logic.
    Decoupled from Transport Layer (handled by Transport adapters).
    """
    def __init__(self, sandbox_root: str):
        self.sandbox_root = sandbox_root
        
        # 1. Initialize Components
        self.policy_guard = PolicyGuard(sandbox_root)
        self.idempotency_cache = IdempotencyCache()
        self.dispatcher = Dispatcher(self.policy_guard)
        
        logger.info(f"AgentServer initialized with sandbox: {sandbox_root}")

    def process_request(self, client_id: str, data: bytes) -> bytes:
        """
        Core Pipeline:
        1. Decode Header
        2. Check Idempotency
        3. Dispatch
        4. Store Result
        """
        try:
            # 1. Transport -> Decoder
            header = decode_header(data[:12])
            payload = data[12:]
            
            # Sub-step: Validate Payload Length against Header
            if len(payload) != header.payload_len:
                logger.warning(f"Payload length mismatch: Header={header.payload_len}, Actual={len(payload)}")
                # We can either reject or trust decoder. 
                # decode_header checks MAX_PAYLOAD_LEN but not actual buffer size match.
                # Let's be strict.
                raise ValueError("Payload length mismatch")

            # 2. Idempotency Check
            cached_response = self.idempotency_cache.get_response(
                client_id, header.request_id, header.opcode
            )
            if cached_response:
                logger.info(f"Returning cached response for ReqID={header.request_id}")
                return cached_response

            # 3. Policy & Dispatch
            # Note: PolicyGuard is used inside handlers/dispatcher, but we could enforce global policies here.
            # (e.g. global rate limit, blocklist - not in Day 2 scope)

            response_bytes = self.dispatcher.dispatch(header, payload)
            
            # 4. Store Result
            self.idempotency_cache.store_response(
                client_id, header.request_id, header.opcode, response_bytes
            )
            
            return response_bytes

        except ValueError as e:
            logger.error(f"Validation Error: {e}")
            # Malformed request - Cannot rely on RequestID if header decode failed.
            # If header failed, we can't reliably send an App Envelope response.
            # We might drop or send a generic error if possible.
            # Taking a safe approach: Return empty or specialized error if possible.
            # But without a parsed RequestID, we can't associate the error.
            # For this implementation, we re-raise or return None to imply "Drop".
            # RUDP/TCP transport might handle "connection close" or "log error".
            return b''  # Drop/Ignore malformed

        except Exception as e:
            logger.error(f"Unexpected Server Error: {e}", exc_info=True)
            return b''
