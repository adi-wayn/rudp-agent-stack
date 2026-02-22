import os
from common.constants import OP_LIST, OP_GET, OP_APPEND, OP_UPLOAD
from client.cli.prompts import prompt_text

def check_conn(state) -> bool:
    if not state.is_connected or not state.agent_client:
        print("⚠️  \033[33mNot connected. Please connect first.\033[0m")
        return False
    return True

def action_list(state, execute_func):
    if not check_conn(state): return
    print("\n[LIST] Files on Server:")
    try:
        res = execute_func("LIST Files", OP_LIST)
        if not res: return
        
        if res.status >= 300:
            print(f"❌ LIST Failed: {res.status} {res.error}")
            return
        
        files = res.data if res.data else []
        print("\033[1;30m────────────────────────────────────────────\033[0m")

        if not files:
            print("⚠️  No files found in sandbox.")
        else:
            print(f"\033[1m{'#':<4} {'Name':<25} {'Size (bytes)':>12}\033[0m")
            print("\033[1;30m────────────────────────────────────────────\033[0m")
            for idx, f in enumerate(files, 1):
                if isinstance(f, dict):
                    name = f.get("name", "UNKNOWN")
                    size = f.get("size", 0)
                    print(f"\033[36m{idx:<4} {name:<25}\033[0m \033[32m{size:>12}\033[0m")
                else:
                    print(f"{idx:<4} {str(f):<25}")
        print("\033[1;30m────────────────────────────────────────────\033[0m")
    except Exception as e:
        print(f"❌ LIST Failed: {e}")

def action_get(state, execute_func, preview_func):
    if not check_conn(state): return
    path = prompt_text("Remote Filename", required=True)
    if not path: return
    
    try:
        res = execute_func("GET File", OP_GET, filename=path)
        if not res: return
        
        if res.status >= 300:
             print(f"❌ GET Failed: {res.status} {res.error}")
             return

        content = res.data
        local_path = os.path.join(state.download_dir, os.path.basename(path))
        with open(local_path, "wb") as f:
            f.write(content)
        print(f"✅ Saved to: {local_path}")
        preview_func(content)
    except Exception as e:
         print(f"❌ GET Failed: {e}")

def action_append(state, execute_func):
    if not check_conn(state): return
    path = prompt_text("Remote Filename", required=True)
    data = prompt_text("Data to Append", required=True)
    
    try:
        res = execute_func("APPEND to File", OP_APPEND, filename=path, data=data.encode())
        if not res: return
        
        if res.status >= 300:
            print(f"❌ APPEND Failed: {res.status} {res.error}")
            return
        print(f"✅ Append Success: {res.data}")
    except Exception as e:
        print(f"❌ APPEND Failed: {e}")

def action_upload(state, execute_func):
    if not check_conn(state): return
    local_path = prompt_text("Local File Path", required=True)
    if not os.path.exists(local_path):
        print("❌ File doesn't exist.")
        return
        
    dest_path = prompt_text("Remote Filename", default=os.path.basename(local_path))
    
    try:
        res = execute_func("UPLOAD File", OP_UPLOAD, local_path=local_path, remote_name=dest_path)
        if not res: return
        
        if res.status >= 300:
            print(f"❌ Upload Failed: {res.status} {res.error}")
        else:
            print(f"✅ Upload Success: {res.data}")
    except Exception as e:
        print(f"❌ Upload Error: {e}")
