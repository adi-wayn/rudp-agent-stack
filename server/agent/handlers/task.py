"""
Task Handler.
Orchestrates Planner and ToolDispatcher for all TASK opcodes.
"""
import json
import logging
import os
from typing import Dict, Any

from common.app_envelope import AppHeader
from common.errors import ErrorCode
from server.agent.planner import Planner
from server.agent.tool_dispatcher import ToolDispatcher
from server.agent.idempotency import IdempotencyCache
from server.agent.validations import PolicyGuard
from server.agent.response_builder import ResponseBuilder

logger = logging.getLogger(__name__)

# Initialize Planner (Stateless)
planner = Planner()

def handle_task(
    header: AppHeader,
    payload: bytes,
    policy_guard: PolicyGuard,
    tool_dispatcher: ToolDispatcher,
    idempotency_cache: IdempotencyCache,
    client_address: tuple = None
) -> Dict[str, Any]:
    """
    Handle all TASK requests.
    
    Flow:
    1. Parse & Validate Payload.
    2. Idempotency Check (if cached).
    3. Build Context (Stat file).
    4. Plan Phase (Planner).
    5. Execute Phase (ToolDispatcher).
    6. Cache & Return.
    """
    try:
        task_data = json.loads(payload.decode('utf-8'))
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON payload")

    # 1. Validation (Schema)
    # Basic field check only, deeper validation in plan
    if not isinstance(task_data, dict):
          raise ValueError("Payload must be a JSON object")

    # 3. Build Context (Moved up for Idempotency Key)
    if client_address:
         client_id = f"{client_address[0]}:{client_address[1]}"
    else:
         client_id = "default_client"

    context = {
        "client_id": client_id,
        "request_id": str(header.request_id)
    }
          
    # 2. Idempotency Check (Pre-Execution)
    # If request_id exists and side_effects=True (cached), return it.
    # Note: Currently IdempotencyCache only caches if we explicitly tell it to.
    # If we have a hit, we return immediately.
    # We pass opcode because cache is keyed by (client, req_id, opcode)
    cached_result = idempotency_cache.get_response(context["client_id"], header.request_id, header.opcode)
    if cached_result:
        logger.info(f"Idempotency Hit: {header.request_id}")
        return cached_result

    # Stat file if target exists to help Planner decision
    if "input_file" in task_data:
        path = task_data["input_file"]
        # Basic sandbox check before stat
        policy_guard.validate_path(path)
        if os.path.exists(path):
            context["file_size"] = os.path.getsize(path)
        else:
            # Task might fail later, or file depends on previous step?
            # For Day 5, target_file is usually input.
            pass

    # 4. Plan Phase
    plan = planner.build_plan(header.opcode, task_data, context)
    
    # Store plan in context for tool usage (e.g. serialize plan artifact)
    context["__plan__"] = plan

    logger.info(f"Built Plan {plan.plan_id} with {len(plan.steps)} steps. Mode: {plan.execution_mode}")

    # 5. Execute Phase
    result = tool_dispatcher.execute_plan(plan)
    
    # 6. Cache & Return
    # Build the final response bytes immediately
    response_bytes = ResponseBuilder.build_response(
        opcode=header.opcode,
        request_id=header.request_id,
        status_code=ErrorCode.OK,
        data=result
    )

    if plan.side_effects:
        idempotency_cache.store_response(context["client_id"], header.request_id, header.opcode, response_bytes)
        
    return response_bytes
