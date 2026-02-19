"""
Unit Tests for Agent Planner.
Verifies deterministic decision making, plan structure, and template assignment.
"""
import pytest
from common.constants import (
    OP_TASK_SEARCH_REPORT,
    OP_TASK_FILTER_LINES,
    OP_TASK_HASH_AND_STORE
)
from server.agent.planner import Planner, ExecutionMode, OutputPolicy, ToolName

@pytest.fixture
def planner():
    return Planner()

@pytest.fixture
def context():
    return {
        "client_id": "test_client",
        "request_id": 12345,
        "file_size": 1000
    }

def test_planner_search_report_memory_inline(planner, context):
    """Test SEARCH_REPORT for small file (Memory Mode)."""
    payload = {"input_file": "/tmp/test.txt", "query": "foo"}
    opcode = OP_TASK_SEARCH_REPORT
    
    plan = planner.build_plan(opcode, payload, context)
    
    assert plan.plan_id is not None
    assert plan.task_type == opcode
    assert plan.execution_mode == ExecutionMode.MEMORY
    assert plan.output_policy == OutputPolicy.DYNAMIC
    assert len(plan.steps) == 3
    assert plan.steps[0].tool == ToolName.READ_FILE
    assert plan.steps[1].tool == ToolName.SEARCH_LINES
    assert plan.steps[2].tool == ToolName.BUILD_REPORT

def test_planner_search_report_stream_mode(planner, context):
    """Test SEARCH_REPORT for large file (Stream Mode)."""
    context['file_size'] = 300 * 1024 # > 256KB
    payload = {"input_file": "/tmp/large.txt", "query": "foo"}
    opcode = OP_TASK_SEARCH_REPORT
    
    plan = planner.build_plan(opcode, payload, context)
    
    assert plan.execution_mode == ExecutionMode.STREAM
    assert plan.steps[0].tool == ToolName.STREAM_READ

def test_planner_filter_lines_with_outfile(planner, context):
    """Test FILTER_LINES with output file (Side Effects)."""
    payload = {
        "input_file": "/tmp/input.txt",
        "query": "bar",
        "out_file": "/tmp/output.txt"
    }
    opcode = OP_TASK_FILTER_LINES
    
    plan = planner.build_plan(opcode, payload, context)
    
    # Should contain READ, FILTER, WRITE, REPORT
    assert len(plan.steps) == 4
    assert plan.steps[2].tool == ToolName.WRITE_FILE
    assert plan.side_effects is True

def test_planner_filter_lines_no_outfile(planner, context):
    """Test FILTER_LINES without output file (No explicit side effects unless fallback)."""
    payload = {
        "input_file": "/tmp/input.txt",
        "query": "bar"
    }
    opcode = OP_TASK_FILTER_LINES
    
    plan = planner.build_plan(opcode, payload, context)
    
    # READ, FILTER
    assert len(plan.steps) == 2
    assert plan.side_effects is False # Unless artifact fallback happens at runtime

def test_planner_hash_and_store(planner, context):
    """Test HASH_AND_STORE (Always side effects)."""
    payload = {
        "input_file": "/tmp/target.bin",
        "out_file": "/tmp/hash.txt"
    }
    opcode = OP_TASK_HASH_AND_STORE
    
    plan = planner.build_plan(opcode, payload, context)
    
    assert plan.side_effects is True
    # STREAM_READ, HASH, WRITE, REPORT
    assert plan.steps[0].tool == ToolName.STREAM_READ
    assert plan.steps[1].tool == ToolName.HASH_SHA256
    assert plan.steps[2].tool == ToolName.WRITE_FILE

def test_planner_return_plan_artifact(planner, context):
    """Test optional plan artifact generation."""
    payload = {
        "input_file": "/tmp/test.txt",
        "query": "foo",
        "options": {"return_plan": True}
    }
    opcode = OP_TASK_SEARCH_REPORT
    
    plan = planner.build_plan(opcode, payload, context)
    
    # Last step should be WRITE_ARTIFACT
    last_step = plan.steps[-1]
    assert last_step.tool == ToolName.WRITE_ARTIFACT
    assert last_step.args['content_key'] == "__PLAN_JSON__"

def test_planner_determinism(planner, context):
    """Test that same input produces same plan_id."""
    payload = {"input_file": "/tmp/same.txt", "query": "same"}
    opcode = OP_TASK_SEARCH_REPORT
    
    plan1 = planner.build_plan(opcode, payload, context)
    plan2 = planner.build_plan(opcode, payload, context)
    
    assert plan1.plan_id == plan2.plan_id

def test_artifact_naming_determinism(planner, context):
    """Test that artifact paths are constructed correctly in logic (implicit in context logic)."""
    # This logic is inside the methods, e.g. return_plan or fallback logic if we exposed it.
    # We can inspect the args of the plan artifact step to see the path pattern.
    payload = {
        "target_file": "/tmp/test.txt",
        "pattern": "foo",
        "options": {"return_plan": True}
    }
    opcode = OP_TASK_SEARCH_REPORT
    
    plan = planner.build_plan(opcode, payload, context)
    artifact_path = plan.steps[-1].args['path']
    
    expected = f"artifacts/{context['client_id']}/{context['request_id']}_plan.json"
    assert artifact_path == expected
