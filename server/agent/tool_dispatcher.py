"""
Tool Dispatcher.
Executes the sequential steps defined in a Plan.
"""
import os
import hashlib
import json
import logging
import tempfile
import shutil
from typing import Dict, Any, Generator, Union

from common.constants import MAX_FILE_SIZE, MAX_PAYLOAD_LEN
from common.errors import ErrorCode, RUDPError
from server.agent.planner import Plan, Step, ToolName, OutputPolicy
from server.agent.validations import PolicyGuard

logger = logging.getLogger(__name__)

# Output Limit for Inline Response (64KB)
INLINE_LIMIT = 64 * 1024

class ToolDispatcher:
    """
    Executes a Plan by dispatching tools and managing context.
    """
    def __init__(self, policy_guard: PolicyGuard):
        self.policy_guard = policy_guard

    def execute_plan(self, plan: Plan) -> Dict[str, Any]:
        """
        Execute the plan steps sequentially.
        Returns the final result dictionary to be sent in the response.
        """
        context = plan.initial_context.copy()
        
        # Track created artifacts/files for cleanup on error if needed?
        # For now, we assume atomic writes handle individual file integrity.
        
        for step in plan.steps:
            try:
                self._execute_step(step, context)
            except Exception as e:
                logger.error(f"Step {step.tool} failed: {e}")
                raise

        # Finalize Output
        # Determine what to return based on output_policy and context
        # Typically the last step produces "final_output" or similar.
        
        result = {}
        
        # If 'output_policy' is ARTIFACT, we expect an artifact path in context?
        # Or if DYNAMIC, we check size.
        
        # Default behavior: Look for "final_output" in context.
        final_output = context.get("final_output")
        
        if final_output:
            # Check size for Inline vs Artifact
            encoded_output = str(final_output).encode('utf-8') # Simplistic serialization check
            
            if plan.output_policy == OutputPolicy.INLINE:
                if len(encoded_output) > INLINE_LIMIT:
                    raise ValueError("Output exceeded inline limit but policy is INLINE")
                result["output"] = final_output
                
            elif plan.output_policy == OutputPolicy.ARTIFACT:
                 # It should have been written to artifact already?
                 # If not, we must write it now.
                 if "artifact_path" not in context:
                     # Fallback: Write now
                     path = self._write_fallback_artifact(encoded_output, context)
                     result["artifact_path"] = path
                 else:
                     result["artifact_path"] = context["artifact_path"]

            else: # DYNAMIC
                if len(encoded_output) <= INLINE_LIMIT:
                     result["output"] = final_output
                else:
                     # Fallback to artifact
                     logger.info("Output too large for inline, falling back to artifact.")
                     path = self._write_fallback_artifact(encoded_output, context)
                     result["artifact_path"] = path

        # If side effects (files written), include their paths if stored in context
        # The prompt says "return_plan" should return "plan_artifact_path".
        if "plan_artifact_path" in context:
             result["plan_artifact_path"] = context["plan_artifact_path"]

        logger.info(f"Tool Dispatcher Execution Completed. Policy={plan.output_policy.value}. Final Output Bytes={len(str(final_output).encode('utf-8')) if final_output else 0}")
        return result

    def _execute_step(self, step: Step, context: Dict[str, Any]):
        """Dispatch single step."""
        tool_name = step.tool
        args = step.args
        
        # Resolve Input
        input_data = None
        if step.consumes:
            if step.consumes not in context:
                 raise ValueError(f"Step {tool_name} requires {step.consumes} which is missing from context.")
            input_data = context[step.consumes]

        output = None

        if tool_name == ToolName.READ_FILE:
            output = self._tool_read_file(args, input_data)
        elif tool_name == ToolName.STREAM_READ:
            output = self._tool_stream_read(args)
        elif tool_name == ToolName.SEARCH_LINES:
            output = self._tool_search_lines(args, input_data)
        elif tool_name == ToolName.FILTER_LINES:
            output = self._tool_filter_lines(args, input_data)
        elif tool_name == ToolName.HASH_SHA256:
            output = self._tool_hash_sha256(args, input_data)
        elif tool_name == ToolName.WRITE_FILE:
            output = self._tool_write_file(args, input_data)
        elif tool_name == ToolName.WRITE_ARTIFACT:
            output = self._tool_write_artifact(args, input_data, context)
        elif tool_name == ToolName.BUILD_REPORT:
            output = self._tool_build_report(args, input_data)
        else:
            raise ValueError(f"Unknown Tool: {tool_name}")

        # Store Output
        if step.produces:
            context[step.produces] = output

    # --------------------------------------------------------------------------
    # Output Utils
    # --------------------------------------------------------------------------
    def _write_fallback_artifact(self, content: bytes, context: Dict) -> str:
        """Write content to a fallback artifact path."""
        # We need a deterministic path if possible, or a safe default.
        # Plan usually has rules for this.
        # We can construct one from client_id/request_id if in context.
        client_id = context.get('client_id', 'unknown')
        request_id = context.get('request_id', 'fallback')
        
        path = f"artifacts/{client_id}/{request_id}_result.txt"
        self._atomic_write(path, content)
        return path

    def _atomic_write(self, path: str, content: Union[str, bytes]):
        """Write file atomically using temp file + rename."""
        # Validation
        safe_path = self.policy_guard.validate_path(path)
        
        # Ensure directory exists
        dirname = os.path.dirname(safe_path)
        os.makedirs(dirname, exist_ok=True) # Recursive create
        
        mode = 'wb' if isinstance(content, bytes) else 'w'
        
        # Temp File
        # We use strict=True in Dispatcher logic, but here we just need to ensure atomic write.
        # NamedTemporaryFile delete=False is needed to close then rename.
        
        # Use same dir for temp file to ensure atomic rename (same filesystem)
        try:
            with tempfile.NamedTemporaryFile(mode, dir=dirname, delete=False) as tmp:
                tmp.write(content)
                tmp.flush()
                try:
                    os.fsync(tmp.fileno())
                except OSError:
                    pass # Some systems don't support fsync on all FDs
                tmp_name = tmp.name
                
            # Rename
            os.replace(tmp_name, safe_path)
            
        except Exception:
            if 'tmp_name' in locals() and os.path.exists(tmp_name):
                os.remove(tmp_name)
            raise

    # --------------------------------------------------------------------------
    # Tools
    # --------------------------------------------------------------------------
    def _tool_read_file(self, args: Dict, input_data: Any) -> str:
        path = args['path']
        safe_path = self.policy_guard.validate_path(path)
        
        # Check size? Plan should have decided mode based on size.
        # But good to enforce limit here too.
        if os.path.getsize(safe_path) > MAX_FILE_SIZE:
             raise ValueError(f"File {safe_path} too large for READ_FILE. Use Streaming.")
             
        with open(safe_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _tool_stream_read(self, args: Dict) -> Generator[Union[str, bytes], None, None]:
        path = args['path']
        binary = args.get('binary', False)
        safe_path = self.policy_guard.validate_path(path)
        
        def file_yielder():
            mode = 'rb' if binary else 'r'
            kwargs = {} if binary else {'encoding': 'utf-8'}
            # Handle unicode decode errors gracefully if someone opens a binary as text
            if not binary: kwargs['errors'] = 'replace'
            with open(safe_path, mode, **kwargs) as f:
                if binary:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        yield chunk
                else:
                    for line in f:
                        yield line
        return file_yielder()

    def _tool_search_lines(self, args: Dict, input_data: Any) -> list:
        pattern = args['pattern']
        # input_data can be str (memory) or generator (stream)
        results = []
        
        iterable = input_data.splitlines() if isinstance(input_data, str) else input_data
            
        for i, line in enumerate(iterable):
            if pattern in line:
                if isinstance(line, str):
                     line = line.strip()
                results.append(f"Line {i+1}: {line}")
                # Cap results?
                if len(results) > 1000: # Arbitrary cap to prevent explosion
                     results.append("... (Truncated)")
                     break
        return results

    def _tool_filter_lines(self, args: Dict, input_data: Any) -> list:
        pattern = args['pattern']
        results = []
        
        iterable = input_data.splitlines() if isinstance(input_data, str) else input_data

        for line in iterable:
            if pattern in line: # Simple substring filter
                results.append(line)
        
        return results

    def _tool_hash_sha256(self, args: Dict, input_data: Any) -> str:
        # If stream, we need to read bytes?
        # If input_data is text generator, we encode? 
        # HASH_AND_STORE usually works on files. The input might be file content or file stream.
        # But the templates in `planner.py` use `STREAM_READ` which opens with 'r' (text).
        # Hashing usually wants bytes.
        # We should update `_tool_stream_read` to support binary?
        # Or Just encode line by line?
        # Encoding line by line might produce different hash due to newline handling?
        # Ideally, HASH_SHA256 reads raw file.
        
        # Let's fix `_tool_stream_read` or handle generic iterable.
        # If it's a file stream, we iterate.
        sha = hashlib.sha256()
        
        iterable = input_data.splitlines(keepends=True) if isinstance(input_data, str) else input_data
        
        for chunk in iterable:
            if isinstance(chunk, str):
                chunk = chunk.encode('utf-8')
            sha.update(chunk)
            
        return sha.hexdigest()

    def _tool_write_file(self, args: Dict, input_data: Any) -> str:
        path = args['path']
        # input_data is content
        
        # Convert list to string if needed
        content = input_data
        if isinstance(content, list):
             content = "\n".join(str(x) for x in content)
             
        self._atomic_write(path, content)
        return "SUCCESS"

    def _tool_write_artifact(self, args: Dict, input_data: Any, context: Dict) -> str:
        path = args['path']
        content_key = args.get('content_key')
        
        # If content_key is special "__PLAN_JSON__", we inject context['plan']?
        # No, context doesn't have the plan object directly usually.
        # But we can pass it if we want.
        # Or we just assume input_data is valid?
        
        content = input_data
        
        if content_key == "__PLAN_JSON__":
             # Special case: Serialize the plan from context (if we stored it?)
             # The Planner didn't put the plan object in context.
             # We might need to adjust the Planner to store 'current_plan' in context?
             # Or we can just use input_data if pass it.
             # Ah, `Step` consumes `None`, implies it doesn't need input data.
             # We should probably pass the Plan object to `execute_plan` context?
             if "__plan__" in context:
                 content = json.dumps(asdict(context["__plan__"]), indent=2, default=str)
             else:
                 content = "{}"
        
        elif content is None and content_key:
             # Look up in context
             content = context.get(content_key)
             
        if content is None:
             content = ""
             
        # Convert list/dict to string
        if isinstance(content, (list, dict)):
             content = json.dumps(content, indent=2, default=str)
             
        self._atomic_write(path, content)
        return path

    def _tool_build_report(self, args: Dict, input_data: Any) -> str:
        fmt = args.get('format')
        msg = args.get('msg')
        
        if fmt == 'action_completion':
            return msg or "Action Completed"
            
        elif fmt == 'search_summary':
            # input_data is list of matches
            count = len(input_data)
            lines = "\n".join(input_data)
            return f"Search Found {count} matches:\n{lines}"
            
        return str(input_data)
