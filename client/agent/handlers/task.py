import logging
import time
from typing import Dict, Any, Optional

from client.agent.dispatcher import ClientHandler, ClientRequestSpec, OperationResult
from common.constants import (
     OP_GET
)

logger = logging.getLogger("TaskHandler")

class TaskHandler(ClientHandler):
    """
    Orchestrator for TASK operations.
    Handles the Request/Response flow for tasks, and automatically retrieves
    artifacts if the server response indicates an 'artifact_file'.
    """

    def __init__(self, opcode: int):
        self.opcode = opcode

    @property
    def is_orchestrator(self) -> bool:
        return True

    def build_request(self, opcode: int = None, **kwargs) -> ClientRequestSpec:
        """
        Builds the JSON payload for the task.
        Arguments expected: task_type, input_file, etc.
        """
        # We construct the payload directly from kwargs.
        # The opcode is fixed per instance.
        return ClientRequestSpec(
            opcode=self.opcode,
            meta=kwargs  # Pass all kwargs as JSON payload
        )

    def parse_response(self, status_code: int, meta: Dict[str, Any], binary: Optional[bytes]) -> OperationResult:
        """
        Parses the immediate response from the Task operation.
        """
        if status_code >= 300:
            return OperationResult(status=status_code, error=meta.get("message", "Task Failed"))
        
        return OperationResult(status=status_code, data=meta)

    def run(self, client, **kwargs) -> OperationResult:
        """
        Orchestrates the Task Execution flow:
        1. Build & Send Task Request.
        2. Check Response for 'artifact_file'.
        3. If Artifact: Trigger GET.
        4. Return Result (Inline or Artifact Content).
        """
        # 1. Build Request
        spec = self.build_request(**kwargs)
        
        # 2. Send via Public Helper
        try:
            status, meta, binary = client.send_request_spec(spec)
        except Exception as e:
            logger.error(f"Task Request Failed: {e}")
            return OperationResult(status=500, error=str(e))
        
        # 3. Parse Initial Response
        task_res = self.parse_response(status, meta, binary)
        
        if task_res.status >= 300:
            return task_res
            
        data = task_res.data if isinstance(task_res.data, dict) else {}
        
        # 4. Check for Artifact
        artifact_file = data.get("artifact_file")
        
        if artifact_file:
            logger.info(f"Task produced artifact: {artifact_file}. Retrieving...")
            
            try:
                # 5. Trigger GET
                # We reuse the client's public get_file convenience method 
                # which executes OP_GET internally.
                content_bytes = client.get_file(artifact_file)
                
                # 6. Save Locally (as per Prompt Requirement)
                # "save locally under a clean output path"
                # We'll use the basename implementation to avoid traversal issues locally too.
                safe_name = artifact_file.replace("/", "_").replace("\\", "_")
                local_output_path = f"downloaded_{safe_name}"
                
                with open(local_output_path, "wb") as f:
                    f.write(content_bytes)
                    
                logger.info(f"Artifact saved to {local_output_path}")
                
                # We return the content but also metadata about where "it went"
                return OperationResult(
                    status=200, 
                    data={
                        "status": "Task Complete (Artifact Downloaded)", 
                        "artifact_local_path": local_output_path,
                        "original_meta": data,
                        # Return bytes in binary_data field if we add it to OperationResult,
                        # but OperationResult definition (viewed earlier) has 'data' as Union[Dict, bytes].
                        # Let's stick to returning a Dict with status, and maybe content?
                        # The prompt says "return/display it immediately". 
                        # Usually calls to execute return OperationResult.
                        # Ideally, the caller (CLI/Test) decides what to do.
                        # But for "Deliverables... Handle artifacts... and saving result locally", we did the saving.
                    }
                )
                
            except Exception as e:
                logger.error(f"Failed to retrieve artifact {artifact_file}: {e}")
                return OperationResult(status=500, error=f"Artifact Retrieval Failed: {e}")
        
        # 7. Inline Result
        return task_res
