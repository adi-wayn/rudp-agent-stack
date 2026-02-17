import hashlib
import logging
from client.agent.dispatcher import ClientHandler, OperationResult, ClientRequestSpec
from client.agent.upload_client import UploadClient
from common.constants import OP_PUT_META, OP_PUT_CHUNK

logger = logging.getLogger("UploadHandler")

class UploadHandler(ClientHandler):
    """
    High-Level Orchestrator for File Uploads.
    Breaks down the upload process into sub-operations (PUT_META, PUT_CHUNK)
    and executes them via the AgentClient.
    """
    
    @property
    def is_orchestrator(self) -> bool:
        return True

    def build_request(self, **kwargs) -> ClientRequestSpec:
        raise NotImplementedError("UploadHandler is an orchestrator and does not build single requests.")

    def parse_response(self, status_code, meta, binary) -> OperationResult:
        raise NotImplementedError("UploadHandler does not parse single responses.")

    def run(self, client, local_path: str, remote_name: str) -> OperationResult:
        """
        Orchestrates the upload flow.
        1. Validates file (via UploadClient).
        2. Initiates Session (OP_PUT_META).
        3. Uploads Chunks (OP_PUT_CHUNK) with retry-safe Request IDs.
        """
        orchestrator = UploadClient()

        # 1. Validation
        error = orchestrator.validate_file(local_path)
        if error:
            return OperationResult(status=400, error=error)

        file_name, file_size = orchestrator.get_file_info(local_path)
        logger.info(f"Starting upload: {local_path} -> {remote_name} ({file_size} bytes)")

        # 2. PUT_META (Session Init)
        # We rely on AgentClient's internal retry for this single op, 
        # or we could implement loop here if we wanted custom backoff, 
        # but client.execute() handles transport retries.
        
        meta_res = client.execute(
            OP_PUT_META, 
            filename=remote_name, 
            total_size=file_size, 
            overwrite=True
        )
        
        if meta_res.status != 200:
            return meta_res
            
        data = meta_res.data if isinstance(meta_res.data, dict) else {}
        upload_id = data.get("upload_id")
        if not upload_id:
             return OperationResult(status=500, error="Server did not return upload_id")

        # 3. PUT_CHUNK Loop
        try:
            for offset, chunk_data in orchestrator.get_chunks(local_path):
                # Generate Stable Request ID for Idempotency
                # hash(upload_id + offset) -> int
                stable_req_id = self._generate_chunk_req_id(upload_id, offset)
                
                chunk_res = client.execute(
                    OP_PUT_CHUNK,
                    upload_id=upload_id,
                    offset=offset,
                    chunk_data=chunk_data,
                    request_id_override=stable_req_id 
                )
                
                if chunk_res.status != 200:
                    logger.error(f"Chunk upload failed at offset {offset}: {chunk_res.error}")
                    return chunk_res
                
                logger.debug(f"Chunk uploaded: offset={offset}")
                
        except Exception as e:
            logger.error(f"Upload failed during chunking: {e}")
            return OperationResult(status=500, error=str(e))

        return OperationResult(status=200, data={"status": "Upload Complete", "size": file_size})

    def _generate_chunk_req_id(self, upload_id: str, offset: int) -> int:
        """
        Generates a deterministic 32-bit integer request ID based on upload_id and offset.
        This ensures that if we retry this specific chunk operation (even at application level),
        we can reuse the ID.
        """
        raw = f"{upload_id}:{offset}".encode("utf-8")
        # SHA256 -> int -> modulo 2^31 (positive int for req_id)
        return int(hashlib.sha256(raw).hexdigest(), 16) % (2**31)
