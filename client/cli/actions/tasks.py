import json
from common.constants import OP_TASK_SEARCH_REPORT, OP_TASK_FILTER_LINES, OP_TASK_HASH_AND_STORE
from client.cli.prompts import prompt_text, prompt_yes_no
from client.cli.ui import print_task_guide, trigger_artifact_download, print_status
from client.cli.actions.file_ops import check_conn

def exec_task(state, execute_func, action_name: str, opcode: int, **kwargs):
    try:
        result = execute_func(action_name, opcode, **kwargs)
        if not result: return
        
        req_id = state.last_request_id if state.last_request_id else 0
        
        if result.status < 300:
            print_status(result.status, req_id, "Task execution responded successfully.")
            handle_result_data(state, result.data)
        else:
            print_status(result.status, req_id, f"Task Failed: {result.error}", False)
        
    except Exception as e:
        print(f"❌ \033[31mExecution Error:\033[0m {e}")

def handle_result_data(state, data: dict):
    inner_data = data.get("data", {}) if isinstance(data, dict) else {}
    artifact_path = inner_data.get("artifact_path")
    
    if artifact_path:
        print(f"\n⚠️  \033[33mResult too large. Artifact generated at server:\033[0m {artifact_path}")
        print("⬇️  Auto-downloading...")
        trigger_artifact_download(state, artifact_path)
        return

    output = inner_data.get("output")
    if output:
        print("\n\033[1;30m--- Result Output ---\033[0m")
        print(output)
        print("\033[1;30m---------------------\033[0m")
    else:
        print("\n\033[1mSummary:\033[0m Task completed successfully.")
        
    if prompt_yes_no("Show raw JSON?", default="N"):
         print(f"\n{json.dumps(data, indent=2)}")

def action_task_search(state, execute_func):
    if not check_conn(state): return
    
    print_task_guide(
        title="TASK: SEARCH_REPORT",
        description="Searches a remote file for a text pattern and returns matching lines.",
        inputs=["Remote file path (e.g., data.txt)", "Search text (e.g., error)"],
        outputs=["Prints matching lines inline", "If output is large, automatically downloads it as an artifact"],
        notes=[]
    )
    
    fname = prompt_text("Remote file path", required=True)
    if not fname: return
    query = prompt_text("Search text", required=True)
    if not query: return
         
    exec_task(state, execute_func, "TASK: Search Report", OP_TASK_SEARCH_REPORT, input_file=fname, query=query)

def action_task_filter(state, execute_func):
    if not check_conn(state): return
    
    print_task_guide(
        title="TASK: FILTER_LINES",
        description="Streams a remote file, removes lines matching the search text, and saves to a new file.",
        inputs=["Remote source file path", "Text to filter out", "Remote output file path (optional)"],
        outputs=["Status message indicating success", "If output file left blank, an artifact will be downloaded automatically"],
        notes=[]
    )
    
    fname = prompt_text("Remote source file", required=True)
    if not fname: return
    query = prompt_text("Text to filter out", required=True)
    if not query: return
    
    outfile = prompt_text("Save output as (remote)", default="", required=False)
    
    args = {"input_file": fname, "query": query}
    if outfile: args["out_file"] = outfile
    
    exec_task(state, execute_func, "TASK: Filter Lines", OP_TASK_FILTER_LINES, **args)

def action_task_hash(state, execute_func):
     if not check_conn(state): return
     
     print_task_guide(
        title="TASK: HASH_AND_STORE",
        description="Calculates the SHA-256 hash of a remote file.",
        inputs=["Remote file path", "Remote output file path (optional)"],
        outputs=["Prints the hash inline", "If output file is specified, saves hash to that file instead"],
        notes=[]
     )
     
     fname = prompt_text("Remote file path", required=True)
     if not fname: return
          
     outfile = prompt_text("Save hash to (remote)", default=f"{fname}.sha256", required=False)
     
     args = {"input_file": fname}
     if outfile: args["out_file"] = outfile
     
     exec_task(state, execute_func, "TASK: Hash & Store", OP_TASK_HASH_AND_STORE, **args)

def action_replay(state, execute_func):
    if not check_conn(state): return
    if not state.last_request_id or state.last_opcode is None or state.last_kwargs is None:
        print("⚠️  \033[33mNo previous request to replay.\033[0m")
        return

    print(f"\n\033[1;35m[REPLAY]\033[0m Replaying Last Request:")
    print(f" \033[1mAction:\033[0m {state.last_action_name}")
    print(f" \033[1mOpcode:\033[0m {state.last_opcode}")
    print(f" \033[1mReq ID:\033[0m {state.last_request_id}")
    
    kwargs = state.last_kwargs.copy()
    
    if "TASK:" in (state.last_action_name or ""):
        exec_task(state, execute_func, state.last_action_name, state.last_opcode, **kwargs)
    else:
        res = execute_func(state.last_action_name, state.last_opcode, **kwargs)
        if not res: return
        
        req_id = state.last_request_id
        if res.status < 300:
            print_status(res.status, req_id, "Replay Success")
            print(f" \033[32mData:\033[0m {res.data}")
        else:
             print_status(res.status, req_id, f"Replay Failed: {res.error}", False)
