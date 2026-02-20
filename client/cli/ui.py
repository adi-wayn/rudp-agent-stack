import os

def print_banner():
    print("\033[1;36m")
    print("========================================")
    print("   RUDP AGENT CLIENT - INTERACTIVE CLI  ")
    print("========================================")
    print("\033[0m")

def print_header(state):
    print("\n\033[1;30m" + "─" * 45 + "\033[0m")
    status_icon = "✅" if state.is_connected else "❌"
    
    print("\033[1;34m 🌐 Network Setup\033[0m")
    print(f" Client IP:  \033[36m{state.client_ip}\033[0m")
    print(f" Server IP:  \033[36m{state.server_ip}\033[0m (Port: {state.server_port})")
    
    print("\033[1;34m 🔌 Connection Status\033[0m")
    print(f" Transport:  \033[33m{state.transport_mode}\033[0m | Connected: {status_icon}")
    
    print("\033[1;34m 📁 Environment\033[0m")
    print(f" Downloads:  \033[32m{state.download_dir}\033[0m")
    print("\033[1;30m" + "─" * 45 + "\033[0m")

def print_menu():
    print("\n\033[1m ── Network Setup ──\033[0m")
    print("  1. DHCP: Acquire IP")
    print("  2. DNS: Resolve App Server")
    print("  3. Connect to App Server")
    print("  4. Disconnect")
    
    print("\n\033[1m ── File Operations ──\033[0m")
    print("  5. LIST Files")
    print("  6. GET File")
    print("  7. APPEND to File")
    print("  8. UPLOAD File")
    
    print("\n\033[1m ── Task Operations ──\033[0m")
    print("  9. TASK: Search Report")
    print(" 10. TASK: Filter Lines")
    print(" 11. TASK: Hash & Store")
    print(" 12. Replay Last Request (Idempotency)")
    
    print("\n\033[1m ── Utilities ──\033[0m")
    print(" 13. Help / About")
    print("  0. Exit")

def print_status(status_code: int, req_id: int, message: str, is_success: bool = True):
    """Standard response block"""
    icon = "✅" if is_success and status_code < 300 else "❌"
    color = "\033[1;32m" if is_success and status_code < 300 else "\033[1;31m"
    print(f"\n{color}{icon} [{status_code}] ReqID: {req_id} - {message}\033[0m")

def print_task_guide(title: str, description: str, inputs: list, outputs: list, notes: list):
    """User Input Guide instead of raw payload schema"""
    print("\n\033[1;35m" + "══" * 25 + "\033[0m")
    print(f" \033[1;36m{title}\033[0m")
    print(f" \033[3m{description}\033[0m")
    print("\033[1;35m" + "──" * 25 + "\033[0m")
    
    print(" \033[1m📋 Inputs required:\033[0m")
    for item in inputs:
        print(f"   • {item}")
        
    print("\n \033[1m📦 Output expected:\033[0m")
    for item in outputs:
        print(f"   • {item}")
        
    if notes:
        print("\n \033[1mℹ️  Notes:\033[0m")
        for item in notes:
            print(f"   - \033[33m{item}\033[0m")
            
    print("\033[1;35m" + "══" * 25 + "\033[0m\n")

def print_help_panel():
    print("\n" + "═" * 50)
    print(" \033[1;36mℹ️  HELP / ABOUT\033[0m")
    print("═" * 50)
    print(" \033[1m• Auto-Download:\033[0m")
    print("   If a TASK returns an artifact (file > 64KB), the CLI")
    print("   will automatically issue a GET request and preview it.")
    print("\n \033[1m• Idempotency Replay (Option 12):\033[0m")
    print("   Resends the EXACT previous request (same opcode, same")
    print("   arguments, and same Request ID). The server should")
    print("   return the cached response without repeating side-effects.")
    print("═" * 50)

def preview_content(content: bytes, max_lines=20):
    try:
        text = content.decode('utf-8')
        lines = text.splitlines()
        print("\n\033[1;30m--- Preview ---\033[0m")
        for line in lines[:max_lines]:
            print(line)
        if len(lines) > max_lines:
            print(f"\033[33m... ({len(lines) - max_lines} more lines)\033[0m")
        print("\033[1;30m---------------\033[0m")
    except UnicodeDecodeError:
        print("\033[33m[Binary Content - No Preview]\033[0m")

def trigger_artifact_download(state, artifact_path: str):
    from common.constants import OP_GET
    try:
        res = state.agent_client.execute(OP_GET, filename=artifact_path)
        if res.status >= 300:
            print_status(res.status, "N/A", f"Artifact Download Failed: {res.error}", False)
            return
         
        content = res.data
        local_name = f"downloaded_{os.path.basename(artifact_path)}"
        local_path = os.path.join(state.download_dir, local_name)
         
        with open(local_path, "wb") as f:
            f.write(content)
             
        print(f"\n✅ \033[32mDownloaded Artifact:\033[0m {local_path}")
        preview_content(content)
         
    except Exception as e:
        print(f"❌ \033[31mArtifact Download Failed:\033[0m {e}")
