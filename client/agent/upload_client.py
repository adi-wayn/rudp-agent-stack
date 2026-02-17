"""
Client-side Upload Logic.
Implements the specific PUT_META -> PUT_CHUNK flow for Day 3.
Derived from docs/specs/System_Specification.md.
"""
import json
import logging
import os
import time
import random
from typing import Optional, Tuple
from common.app_envelope import encode_message, decode_header, HEADER_SIZE, AppHeader
from common.constants import (
    OP_PUT_META, OP_PUT_CHUNK, MAX_FILE_SIZE, MAX_RETRIES,
    INITIAL_RTO, MAX_RTO, ALPHA, BETA
)

logger = logging.getLogger("UploadClient")

class UploadClient:
    """
    Handles reliable file uploads using the system protocol.
    """
    def __init__(self, transport):
        """
        Args:
            transport: Object with send(bytes) and receive_exact(n) methods.
                       Must implement the Transport abstraction.
        """
        self.transport = transport
        self.request_id_counter = random.randint(1000, 9999)

    def _get_next_request_id(self) -> int:
        self.request_id_counter += 1
        return self.request_id_counter

    def upload_file(self, local_path: str, remote_name: str, chunk_size: int = 8192) -> bool:
        """
        Uploads a local file to the server.
        
        Args:
            local_path: Path to the file on the client machine.
            remote_name: Name of the file on the server.
            chunk_size: Size of chunks to send (default 8KB).
            
        Returns:
            True if upload successful, False otherwise.
        """
        if not os.path.exists(local_path):
            logger.error(f"File not found: {local_path}")
            return False

        file_size = os.path.getsize(local_path)
        if file_size > MAX_FILE_SIZE:
            logger.error(f"File size {file_size} exceeds limit {MAX_FILE_SIZE}")
            return False

        logger.info(f"Starting upload: {local_path} -> {remote_name} ({file_size} bytes)")

        # 1. Send PUT_META
        upload_id = self._send_put_meta(remote_name, file_size)
        if not upload_id:
            logger.error("Failed to initialize upload session (PUT_META failed)")
            return False

        # 2. Send PUT_CHUNK loop
        offset = 0
        with open(local_path, "rb") as f:
            while offset < file_size:
                # Read next chunk
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break

                chunk_len = len(chunk_data)
                
                # Send Chunk with Retry
                if not self._send_put_chunk(upload_id, offset, chunk_data):
                    logger.error(f"Failed to upload chunk at offset {offset}. Aborting.")
                    return False

                # Advance offset only on success
                offset += chunk_len
                logger.info(f"Chunk uploaded: offset={offset}/{file_size}")

        logger.info("Upload completed successfully.")
        return True

    def _send_put_meta(self, filename: str, total_size: int) -> Optional[str]:
        """
        Sends PUT_META request and waits for upload_id.
        Retries on failure.
        """
        meta_payload = {
            "filename": filename,
            "total_size": total_size,
            "overwrite": True
        }
        json_bytes = json.dumps(meta_payload).encode("utf-8")
        
        # Reuse request_id for retries (Idempotency)
        req_id = self._get_next_request_id()

        for attempt in range(MAX_RETRIES):
            try:
                # Encode and Send
                msg = encode_message(OP_PUT_META, 0, req_id, json_bytes)
                self.transport.send_bytes(msg)
                
                # Receive Response
                op, flags, r_id, payload = self._wait_for_response(req_id, timeout=self._calc_timeout(attempt))
                
                # Parse Response (Server wraps in {status, error, data})
                response = json.loads(payload.decode("utf-8"))
                
                # Check Status
                if response.get("status") == 200:
                    data = response.get("data", {})
                    if data and "upload_id" in data:
                        return data["upload_id"]
                
                # Extract Error
                error_msg = response.get("error")
                if error_msg:
                    logger.error(f"Server returned error: {error_msg}")
                    # If it's a domain error (e.g. 409 conflict, 403), retrying might not help, but we follow retry policy.
                    # Unless we want to abort on specific errors? For now, standard retry.
                    # Actually, for 409 (Conflict), we should probably abort?
                    # But verifying specs, client just retries.
                
            except (TimeoutError, ConnectionError, ValueError) as e:
                logger.warning(f"PUT_META attempt {attempt+1}/{MAX_RETRIES} failed: {e}")
                time.sleep(self._calc_backoff(attempt))
                
        return None

    def _send_put_chunk(self, upload_id: str, offset: int, chunk_data: bytes) -> bool:
        """
        Sends a single chunk. Retries on timeout.
        """
        # Construct Payload: JSON Metadata + Raw Bytes
        meta = {
            "upload_id": upload_id,
            "offset": offset,
            "chunk_len": len(chunk_data)
        }
        json_bytes = json.dumps(meta).encode("utf-8")
        
        # Strict concatenation: JSON bytes + Raw bytes
        payload = json_bytes + chunk_data
        
        # Request ID for this chunk (Fixed for all retries of this chunk)
        req_id = self._get_next_request_id()

        for attempt in range(MAX_RETRIES):
            try:
                msg = encode_message(OP_PUT_CHUNK, 0, req_id, payload)
                self.transport.send_bytes(msg)

                # Wait for response
                op, flags, r_id, resp_payload = self._wait_for_response(req_id, timeout=self._calc_timeout(attempt))
                
                # Verify Success
                # Server returns bytes_written, complete, status inside "data"
                resp_json = json.loads(resp_payload.decode("utf-8"))
                
                if resp_json.get("status") == 200:
                    data = resp_json.get("data", {})
                    # Verify bytes_written Matches (Server might not verify? Handler checks it)
                    if data.get("bytes_written") == len(chunk_data):
                        return True
                
                logger.warning(f"Unexpected response: {resp_json}")
                
            except (TimeoutError, ConnectionError, ValueError) as e:
                logger.warning(f"PUT_CHUNK offset={offset} attempt {attempt+1}/{MAX_RETRIES} failed: {e}")
                time.sleep(self._calc_backoff(attempt))
        
        return False

    def _wait_for_response(self, expected_req_id: int, timeout: float) -> Tuple[int, int, int, bytes]:
        """
        Waits for a response matching the request_id.
        """
        start_time = time.time()
        
        # We need a way to set timeout on the socket/transport.
        # Assuming transport is synchronous/blocking with timeout support
        # or we rely on the transport's internal timeout.
        # But we need to implement application-level timeout loop if transport doesn't handle it per-call.
        # For this design, let's assume `transport.sock.settimeout(timeout)` works if it's TCPClient.
        
        if hasattr(self.transport, 'sock') and self.transport.sock:
             self.transport.sock.settimeout(timeout)

        # Basic receive loop - might receive older packets/duplicates in RUDP?
        # In TCP, order is guaranteed, but let's be robust.
        
        try:
            # Reusing the logic from TCPClient.receive_response but we need access to it.
            # If transport has receive_response(), use it.
            # Detailed implementation:
            op, flags, rid, payload = self.transport.receive_response()
            
            if rid == expected_req_id:
                return op, flags, rid, payload
            else:
                # In TCP, receiving wrong ID implies logic error or very old garbage.
                # In RUDP, could be out of order.
                # For Day 3 Client (TCP Baseline), we expect sync response.
                raise ValueError(f"ID Mismatch: Expected {expected_req_id}, got {rid}")
                
        except Exception as e:
            raise TimeoutError(f"Wait failed: {e}")

    def _calc_timeout(self, attempt: int) -> float:
        """Simple exponential backoff for timeout duration."""
        return min(INITIAL_RTO * (2 ** attempt), MAX_RTO)

    def _calc_backoff(self, attempt: int) -> float:
        """Sleep time between retries."""
        return random.uniform(0.1, 0.5) * (2 ** attempt)
