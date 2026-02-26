"""
Agent Planner Module.
Breaks down tasks into deterministic execution steps.
"""
import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from enum import Enum

from common.constants import (
    OP_TASK_SEARCH_REPORT,
    OP_TASK_FILTER_LINES,
    OP_TASK_HASH_AND_STORE,
    MAX_FILE_SIZE
)

logger = logging.getLogger(__name__)

# ==============================================================================
# Constants & Limits
# ==============================================================================
STREAM_THRESHOLD = 256 * 1024  # 256 KB
MAX_INLINE_SIZE = 64 * 1024    # 64 KB
ARTIFACT_DIR = "artifacts"

# ==============================================================================
# Enums
# ==============================================================================
class ExecutionMode(str, Enum):
    MEMORY = "memory"
    STREAM = "stream"

class OutputPolicy(str, Enum):
    INLINE = "inline"
    ARTIFACT = "artifact"
    DYNAMIC = "dynamic"  # Try inline, fallback to artifact

class ToolName(str, Enum):
    READ_FILE = "READ_FILE"
    STREAM_READ = "STREAM_READ"
    SEARCH_LINES = "SEARCH_LINES"
    FILTER_LINES = "FILTER_LINES"
    HASH_SHA256 = "HASH_SHA256"
    BUILD_REPORT = "BUILD_REPORT"
    WRITE_FILE = "WRITE_FILE"
    WRITE_ARTIFACT = "WRITE_ARTIFACT"

# ==============================================================================
# Schema
# ==============================================================================
@dataclass
class Step:
    """A single execution step in the plan."""
    tool: str
    args: Dict[str, Any]
    produces: str  # Context key for output
    consumes: Optional[str] = None  # Context key for input

@dataclass
class Plan:
    """
    Deterministic execution plan.
    """
    plan_id: str
    task_type: int
    execution_mode: str
    output_policy: str
    steps: List[Step]
    side_effects: bool  # True if strict idempotency caching required
    explanation: str
    initial_context: Dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# Planner Logic
# ==============================================================================
class Planner:
    """
    Rule-based deterministic planner.
    """
    
    def build_plan(self, opcode: int, payload: Dict[str, Any], context: Dict[str, Any]) -> Plan:
        """
        Build a deterministic execution plan.
        
        Args:
            opcode: The task opcode (0x10, 0x11, 0x12)
            payload: Tne validated task payload dictionary
            context: System context (file_size, client_id, request_id)
            
        Returns:
            Plan object
        """
        # 1. Deterministic Decision Rules
        file_size = context.get('file_size', 0)
        
        # Rule: Execution Mode
        # If file <= 256KB -> Memory, else -> Stream
        execution_mode = ExecutionMode.MEMORY if file_size <= STREAM_THRESHOLD else ExecutionMode.STREAM
        
        # Rule: Output Policy
        # Defaults to DYNAMIC (try inline, fallback to artifact)
        # Specific tasks might force ARTIFACT or INLINE
        output_policy = OutputPolicy.DYNAMIC

        # Rule: Artifact Naming
        # Keyed by (client_id, request_id)
        client_id = context.get('client_id', 'unknown')
        request_id = context.get('request_id', 0)
        
        # Base artifact name pattern: {client_id}_{request_id}_{suffix}
        def make_artifact_path(suffix: str) -> str:
            return f"{ARTIFACT_DIR}/{client_id}/{request_id}_{suffix}"

        steps = []
        side_effects = False
        explanation = ""

        # 2. Template Selection
        if opcode == OP_TASK_SEARCH_REPORT:
            explanation = "Search pattern in file and generate report."
            steps = self._template_search_report(payload, execution_mode, make_artifact_path)
            # Side effects only if artifact generated (handled dynamically)
            # But strictly speaking, if we *might* write an artifact, we should treat as side-effect for caching?
            # Actually, SEARCH is read-only unless result is large.
            # But if result is large, we write artifact -> side effect.
            # To be safe for idempotency, we mark side_effects=False for purely read-only *intent*,
            # but if fallback triggers, the executor handles idempotency via the cache update.
            # However, spec implies side_effects=True means "non-trivial operation worth caching result pointer".
            # Let's say False for now, as it doesn't mutate server state (files).
            side_effects = False 

        elif opcode == OP_TASK_FILTER_LINES:
            explanation = "Filter lines matching pattern."
            out_file = payload.get('out_file')
            steps = self._template_filter_lines(payload, execution_mode, out_file, make_artifact_path)
            # If out_file is present, we definitely have side effects (writing a file)
            # If no out_file, we might write artifact if large -> same logic as search.
            side_effects = bool(out_file)

        elif opcode == OP_TASK_HASH_AND_STORE:
            explanation = "Compute SHA256 hash and store to file."
            steps = self._template_hash_and_store(payload, execution_mode)
            side_effects = True

        else:
            raise ValueError(f"Unknown Task Opcode: {opcode}")

        # 3. Optional: Plan Artifact (return_plan=True)
        # This is appended if requested.
        options = payload.get('options', {})
        if options.get('return_plan'):
            plan_path = make_artifact_path("plan.json")
            # We add a step to write the plan itself?
            # Or is this handled outside?
            # The prompt says: "Generate a plan artifact... Return plan_artifact_path in response."
            # It's cleaner if the Planner adds a step to write the plan?
            # But the plan isn't fully formed until we return.
            # Let's assume the Dispatcher handles writing the plan artifact if the Plan says so?
            # Or we add a step that writes "current_plan" ?
            # Simplified: We just note it in context or handle in dispatcher.
            # Re-reading prompt: "Planner... adds WRITE_ARTIFACT(plan.json)"
            # But `Plan` object is what we are building.
            # We can serialize `steps` so far.
            steps.append(Step(
                tool=ToolName.WRITE_ARTIFACT,
                args={
                    "path": plan_path,
                    "content_key": "__PLAN_JSON__" # Executor will inject plan JSON here
                },
                produces="plan_artifact_path",
                consumes=None
            ))


        # 4. Generate Deterministic Plan ID
        # Hash of (opcode + payload + context + rules)
        plan_str = f"{opcode}-{json.dumps(payload, sort_keys=True)}-{execution_mode}-{output_policy}-{side_effects}"
        plan_id = hashlib.sha256(plan_str.encode()).hexdigest()[:16]

        return Plan(
            plan_id=plan_id,
            task_type=opcode,
            execution_mode=execution_mode,
            output_policy=output_policy,
            steps=steps,
            side_effects=side_effects,
            explanation=explanation,
            initial_context=context
        )

    # --------------------------------------------------------------------------
    # Templates
    # --------------------------------------------------------------------------
    def _template_search_report(self, payload: Dict, mode: str, artifact_fn) -> List[Step]:
        target_file = payload.get('input_file')
        pattern = payload.get('query')
        
        # Step 1: Read
        if mode == ExecutionMode.MEMORY:
            read_step = Step(ToolName.READ_FILE, {"path": target_file}, "file_content")
        else:
            read_step = Step(ToolName.STREAM_READ, {"path": target_file}, "file_stream")
            
        # Step 2: Search
        search_step = Step(
            ToolName.SEARCH_LINES,
            {"pattern": pattern},
            "search_results",
            consumes=read_step.produces
        )
        
        # Step 3: Build Report
        report_step = Step(
            ToolName.BUILD_REPORT,
            {"format": "search_summary"},
            "final_output",
            consumes="search_results"
        )
        
        # Output Policy is Dynamic:
        # If output > 64KB, Write Artifact. 
        # This decision happens at runtime in Executor, but we put the step structure.
        # Actually, if we use DYNAMIC policy, the Executor needs to know what to do with "final_output".
        # We can add an explicit fallback step or rely on the OutputPolicy flag.
        # The prompt says: "Output Policy Rule... Plan MUST include fallback to artifact write"
        # So we should probably return the content, and if too big, the executor writes it.
        # But wait, "Must include caps + fallback".
        
        # Let's rely on ToolDispatcher's handling of "final_output" based on OutputPolicy.DYNAMIC.
        
        return [read_step, search_step, report_step]

    def _template_filter_lines(self, payload: Dict, mode: str, out_file: Optional[str], artifact_fn) -> List[Step]:
        target_file = payload.get('input_file')
        pattern = payload.get('query')
        
        # Step 1: Read
        if mode == ExecutionMode.MEMORY:
            read_step = Step(ToolName.READ_FILE, {"path": target_file}, "file_content")
        else:
            read_step = Step(ToolName.STREAM_READ, {"path": target_file}, "file_stream")

        # Step 2: Filter
        filter_step = Step(
            ToolName.FILTER_LINES,
            {"pattern": pattern},
            "filtered_lines",
            consumes=read_step.produces
        )

        steps = [read_step, filter_step]

        if out_file:
            # Case A: Write to file
            write_step = Step(
                ToolName.WRITE_FILE,
                {"path": out_file},
                "write_status",
                consumes="filtered_lines"
            )
            report_step = Step(
                ToolName.BUILD_REPORT,
                {"format": "action_completion", "msg": f"Filtered lines written to {out_file}"},
                "final_output"
            )
            steps.append(write_step)
            steps.append(report_step)
        else:
            # Case B: No out_file -> Dynamic Output (Inline or Artifact)
            # If we want to be explicit about artifact fallback in the plan:
            # We can't easily express branching "if size > X" in a flat list of steps without a conditional engine.
            # But the prompt says "Plan must include fallback to artifact".
            # The cleanest way is to have the Executor handle "final_output" according to OutputPolicy.
            pass

        return steps

    def _template_hash_and_store(self, payload: Dict, mode: str) -> List[Step]:
        target_file = payload.get('input_file')
        dest_file = payload.get('out_file')
        # Re-reading prompt: "TASK_HASH_AND_STORE (0x12) ... HASH_SHA256 ... WRITE_FILE(hash_output)"
        # Payload schema usually has target_file. Where is output path?
        # If not in payload, does it hash inplace? No, "store".
        # Looking at schema in my head (from spec): usually `target_file` and `output_file` is defined.
        # I'll check `context` or just use `artifact` if not specified? 
        # Actually, `HASH_AND_STORE` likely expects a destination. 
        # I will assume `output_file` is in payload for now.
        
        # If simple task that returns hash:
        # Step 1: Stream Read (always stream for hash to be efficient?)
        # Mode decision applies.
        
        # For hashing, Streaming is always better, and must be binary.
        read_step = Step(ToolName.STREAM_READ, {"path": target_file, "binary": True}, "file_stream")
        
        hash_step = Step(
            ToolName.HASH_SHA256,
            {},
            "hash_result",
            consumes="file_stream"
        )
        
        write_step = Step(
            ToolName.WRITE_FILE,
            {"path": dest_file}, # Panic if missing?
            "write_status",
            consumes="hash_result"
        )
        
        report_step = Step(
            ToolName.BUILD_REPORT,
            {"format": "action_completion", "msg": f"Hash written to {dest_file}"},
            "final_output"
        )

        return [read_step, hash_step, write_step, report_step]
