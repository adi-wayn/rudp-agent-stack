"""
Interactive CLI for Agent Client.
Provides a menu-driven interface to interact with the Agent Server.
Strictly separates UI logic from Protocol logic.
"""
import os
import sys
import time
import dataclasses
from typing import Optional

# Core Logic Imports (No Transport Imports Here)
from client.agent_client import AgentClient
from client.transport.factory import TransportFactory
from client.dhcp_client import DHCPClient
from client.dns_client import DNSClient
from common.constants import (
    OP_GET, OP_LIST, OP_APPEND, OP_PUT_META, OP_PUT_CHUNK, OP_UPLOAD,
    OP_TASK_SEARCH_REPORT, OP_TASK_FILTER_LINES, OP_TASK_HASH_AND_STORE, INITIAL_RTO
)

# Constants
DEFAULT_DOWNLOAD_DIR = "./downloads"

@dataclasses.dataclass
class SessionState:
    """Tracks the state of the CLI session."""
    client_ip: str = "NOT_SET"
    server_ip: str = "NOT_SET"
    server_port: int = 8080
    transport_mode: str = "TCP"  # TCP or RUDP
    is_connected: bool = False
    
    # Active Client Instance
    agent_client: Optional[AgentClient] = None
    
    # State
    download_dir: str = DEFAULT_DOWNLOAD_DIR
    
    # Replay State
    last_action_name: Optional[str] = None
    last_opcode: Optional[int] = None
    last_kwargs: Optional[dict] = None
    last_request_id: Optional[int] = None
    
class InteractiveCLI:
    """
    Main CLI Controller.
    """
    def __init__(self):
        self.state = SessionState()
        self.running = True
        
        # Ensure download dir exists
        if not os.path.exists(self.state.download_dir):
            os.makedirs(self.state.download_dir)

    def start(self):
        """Main Loop."""
        self._print_banner()
        
        while self.running:
            self._print_header()
            self._print_menu()
            choice = input("\nSelect an option (0-13): ").strip()
            
            try:
                self._handle_choice(choice)
            except Exception as e:
                print(f"\n❌ Error: {e}")
                input("Press Enter to continue...")

    # ==========================
    # UI Helpers
    # ==========================
    def _print_banner(self):
        print("\033[1;36m")
        print("========================================")
        print("   RUDP AGENT CLIENT - INTERACTIVE CLI  ")
        print("========================================")
        print("\033[0m")

    def _print_header(self):
        # Clear screen? Maybe just separator.
        print("\n" + "─" * 40)
        s = self.state
        status_icon = "✅" if s.is_connected else "❌"
        print(f" Client IP:  {s.client_ip}")
        print(f" Server IP:  {s.server_ip} (Port: {s.server_port})")
        print(f" Transport:  {s.transport_mode} | Connected: {status_icon}")
        print(f" Downloads:  {s.download_dir}")
        print("─" * 40)

    def _print_menu(self):
        print(" 1. DHCP: Acquire IP")
        print(" 2. DNS: Resolve App Server")
        print(" 3. Connect to App Server")
        print(" 4. Disconnect")
        print(" ─ File Operations ─")
        print(" 5. LIST Files")
        print(" 6. GET File")
        print(" 7. APPEND to File")
        print(" 8. UPLOAD File")
        print(" ─ Task Operations ─")
        print(" 9. TASK: Search Report")
        print(" 10. TASK: Filter Lines")
        print(" 11. TASK: Hash & Store")
        print(" 12. Replay Last Request (Idempotency)")
        print(" ─ Other ─")
        print(" 13. Help / About")
        print(" 0. Exit")

    def _handle_choice(self, choice: str):
        if choice == "0":
            self.running = False
            print("Goodbye!")
            return
            
        map_action = {
            "1": self._action_dhcp,
            "2": self._action_dns,
            "3": self._action_connect,
            "4": self._action_disconnect,
            "5": self._action_list,
            "6": self._action_get,
            "7": self._action_append,
            "8": self._action_upload,
            "9": self._action_task_search,
            "10": self._action_task_filter,
            "11": self._action_task_hash,
            "12": self._action_replay,
            "13": self._action_help
        }
        
        action = map_action.get(choice)
        if action:
            action()
        else:
            print("Invalid choice.")

    # ==========================
    # Actions
    # ==========================
    def _action_dhcp(self):
        print("\n[DHCP] Discovering...")
        client = DHCPClient()
        try:
            # Real call only
            client.discover()
            print("DHCP Success (Mocked/Real?)") 
            # If skeletons raise NotImplementedError, we catch it.
        except NotImplementedError:
             print("⚠️  DHCP Not Implemented yet.")
             return
        except Exception as e:
             print(f"❌ DHCP Failed: {e}")

    def _action_dns(self):
        print("\n[DNS] Resolving 'app.server'...")
        # We need a DNS server IP. Assume standard or from DHCP?
        # For now prompt or use default
        dns_ip = input("Enter DNS Server IP [127.0.0.1]: ").strip() or "127.0.0.1"
        client = DNSClient(dns_ip)
        try:
            resolved = client.resolve("app.server")
            if resolved:
                self.state.server_ip = resolved
                print(f"✅ Resolved app.server -> {resolved}")
            else:
                print("❌ DNS Resolution failed.")
        except NotImplementedError:
             print("⚠️  DNS Not Implemented yet.")
        except Exception as e:
             print(f"❌ DNS Failed: {e}")

    def _action_connect(self):
        if self.state.server_ip == "NOT_SET":
             print("⚠️  Please resolve Server IP (DNS) first (or manually set).")
             manual = input("Set Server IP manually? [y/N]: ")
             if manual.lower() == 'y':
                 self.state.server_ip = input("Server IP: ").strip()
             else:
                 return

        mode = input(f"Transport Mode (TCP/RUDP) [{self.state.transport_mode}]: ").strip() or self.state.transport_mode
        self.state.transport_mode = mode.upper()
        
        print(f"Connecting to {self.state.server_ip}:{self.state.server_port} via {self.state.transport_mode}...")
        
        try:
            # Use Factory
            transport = TransportFactory.create(
                self.state.transport_mode, 
                self.state.server_ip, 
                self.state.server_port
            )
            # Instantiate Client
            self.state.agent_client = AgentClient(transport)
            
            # Trigger handshake (Transport specific)
            # TCP connects on first send usually, but we can force connect?
            # TCPClient has connect().
            self.state.agent_client.transport.connect(timeout=INITIAL_RTO)
            
            self.state.is_connected = True
            print("✅ Connected!")
            
        except Exception as e:
            print(f"❌ Connection Failed: {e}")
            self.state.is_connected = False
            self.state.agent_client = None

    def _action_disconnect(self):
        if self.state.agent_client:
            self.state.agent_client.close()
        self.state.is_connected = False
        self.state.agent_client = None
        print("Disconnected.")

    def _check_conn(self) -> bool:
        if not self.state.is_connected or not self.state.agent_client:
            print("⚠️  Not connected. Please connect first.")
            return False
        return True

    def _execute_and_remember(self, action_name: str, opcode: int, **kwargs):
        """
        Centralized core execution for the CLI.
        Forces explicit generation of request_id_override to store it for replays.
        """
        req_id = kwargs.get("request_id_override")
        if not req_id:
            req_id = self.state.agent_client.request_id_manager.next_id()
            kwargs["request_id_override"] = req_id
            
            # Store in SessionState for future replays
            self.state.last_action_name = action_name
            self.state.last_opcode = opcode
            self.state.last_kwargs = kwargs.copy()
            self.state.last_request_id = req_id

        print(f"\n⏳ Executing '{action_name}' (ReqID: {req_id})...")
        try:
            return self.state.agent_client.execute(opcode, **kwargs)
        except Exception as e:
            print(f"❌ Execution Error: {e}")
            return None

    def _action_list(self):
        if not self._check_conn(): return
        print("\n[LIST] Files on Server:")
        try:
            res = self._execute_and_remember("LIST Files", OP_LIST)
            if not res: return
            
            if res.status >= 300:
                print(f"❌ LIST Failed: {res.status} {res.error}")
                return
            
            files = res.data if res.data else []
            print("────────────────────────────────────────────")

            if not files:
                print("⚠️  No files found in sandbox.")
            else:
                print(f"{'#':<4} {'Name':<25} {'Size (bytes)':>12}")
                print("────────────────────────────────────────────")
                for idx, f in enumerate(files, 1):
                    if isinstance(f, dict):
                        name = f.get("name", "UNKNOWN")
                        size = f.get("size", 0)
                        print(f"{idx:<4} {name:<25} {size:>12}")
                    else:
                        print(f"{idx:<4} {str(f):<25}")
            
            print("────────────────────────────────────────────")
        except Exception as e:
            print(f"❌ LIST Failed: {e}")

    def _action_get(self):
        if not self._check_conn(): return
        path = input("Remote Filename: ").strip()
        if not path: return
        
        try:
            res = self._execute_and_remember("GET File", OP_GET, filename=path)
            if not res: return
            
            if res.status >= 300:
                 print(f"❌ GET Failed: {res.status} {res.error}")
                 return

            content = res.data
            # Save locally
            local_path = os.path.join(self.state.download_dir, os.path.basename(path))
            with open(local_path, "wb") as f:
                f.write(content)
            print(f"✅ Saved to: {local_path}")
            self._preview_content(content)
        except Exception as e:
             print(f"❌ GET Failed: {e}")

    def _action_append(self):
        if not self._check_conn(): return
        path = input("Remote Filename: ").strip()
        data = input("Data to Append: ").strip()
        
        try:
            res = self._execute_and_remember("APPEND to File", OP_APPEND, filename=path, data=data.encode())
            if not res: return
            
            if res.status >= 300:
                print(f"❌ APPEND Failed: {res.status} {res.error}")
                return
            print(f"✅ Append Success: {res.data}")
        except Exception as e:
            print(f"❌ APPEND Failed: {e}")

    def _action_upload(self):
        if not self._check_conn(): return
        local_path = input("Local File Path: ").strip()
        if not os.path.exists(local_path):
            print("❌ File doesn't exist.")
            return
            
        dest_path = input("Remote Filename (e.g. data.txt): ").strip()
        if not dest_path or dest_path == ".":
             # Fallback to local basename if user types '.' or empty
             dest_path = os.path.basename(local_path)
             print(f"⚠️  Defaulting remote name to: {dest_path}")
        
        try:
            res = self._execute_and_remember("UPLOAD File", OP_UPLOAD, local_path=local_path, remote_name=dest_path)
            if not res: return
            
            if res.status >= 300:
                print(f"❌ Upload Failed: {res.status} {res.error}")
            else:
                print(f"✅ Upload Success: {res.data}")
        except Exception as e:
            print(f"❌ Upload Error: {e}")

    def _action_task_search(self):
        if not self._check_conn(): return
        
        self._print_task_panel(
            task_name="TASK: SEARCH_REPORT",
            description="Searches a remote file for a regex query and returns matching lines.",
            req_fields="input_file, query",
            opt_fields="options (e.g. case_sensitive)",
            example='{"task_type": "SEARCH_REPORT", "input_file": "data.txt", "query": "error", "out_file": null}'
        )
        
        fname = input("Input File: ").strip()
        query = input("Query Pattern: ").strip()
        
        # Don't execute if they just hit enter
        if not fname or not query:
             print("⚠️  Missing required fields. Aborting.")
             return
             
        self._exec_task(
            "TASK: Search Report",
            OP_TASK_SEARCH_REPORT,
            input_file=fname,
            query=query
        )

    def _action_task_filter(self):
        if not self._check_conn(): return
        
        self._print_task_panel(
            task_name="TASK: FILTER_LINES",
            description="Streams a remote file, filters out matching lines, and writes cleanly to out_file.",
            req_fields="input_file, query",
            opt_fields="out_file (creates artifact if null), options",
            example='{"task_type": "FILTER_LINES", "input_file": "raw.log", "query": "debug", "out_file": "clean.log"}'
        )
        
        fname = input("Input File: ").strip()
        query = input("Query Pattern: ").strip()
        
        if not fname or not query:
             print("⚠️  Missing required fields. Aborting.")
             return
             
        outfile = input("Start Output File (optional): ").strip()
        
        args = {"input_file": fname, "query": query}
        if outfile: args["out_file"] = outfile
        
        self._exec_task("TASK: Filter Lines", OP_TASK_FILTER_LINES, **args)

    def _action_task_hash(self):
         if not self._check_conn(): return
         
         self._print_task_panel(
            task_name="TASK: HASH_AND_STORE",
            description="Generates an SHA-256 hash of the input file and stores it in out_file.",
            req_fields="input_file",
            opt_fields="out_file (creates artifact if null), options",
            example='{"task_type": "HASH_AND_STORE", "input_file": "data.bin", "query": null, "out_file": "data.hash"}'
         )
         
         fname = input("Input File: ").strip()
         
         if not fname:
              print("⚠️  Missing required input_file. Aborting.")
              return
              
         outfile = input("Output File: ").strip()
         
         args = {"input_file": fname}
         if outfile: args["out_file"] = outfile
         
         self._exec_task("TASK: Hash & Store", OP_TASK_HASH_AND_STORE, **args)

    def _action_replay(self):
        if not self._check_conn(): return
        s = self.state
        if not s.last_request_id or s.last_opcode is None or s.last_kwargs is None:
            print("⚠️  No previous request to replay.")
            return

        print(f"\n[REPLAY] Replaying Last Request:")
        print(f" Action: {s.last_action_name}")
        print(f" Opcode: {s.last_opcode}")
        print(f" Req ID: {s.last_request_id}")
        
        # We resend the EXACT previous request
        kwargs = s.last_kwargs.copy()
        
        # For task execution responses, we might want to route them through _exec_task again
        # to get artifact auto-download.
        # If it's a task:
        if "TASK:" in (s.last_action_name or ""):
            # Drop the action_name from call since _exec_task expects it first
            self._exec_task(s.last_action_name, s.last_opcode, **kwargs)
        else:
            # Direct operation
            res = self._execute_and_remember(s.last_action_name, s.last_opcode, **kwargs)
            if not res: return
            
            if res.status < 300:
                print(f"✅ Replay Success: {res.data}")
            else:
                 print(f"❌ Replay Failed: {res.status} {res.error}")

    def _action_help(self):
        print("\n" + "═" * 50)
        print(" \033[1;36mℹ️  HELP / ABOUT\033[0m")
        print("═" * 50)
        print(" • Auto-Download:")
        print("   If a TASK returns an artifact (file > 64KB), the CLI")
        print("   will automatically issue a GET request and preview it.")
        print("\n • Idempotency Replay (Option 12):")
        print("   Resends the EXACT previous request (same opcode, same")
        print("   arguments, and same Request ID). The server should")
        print("   return the cached response without repeating side-effects.")
        print("═" * 50)

    def _print_task_panel(self, task_name: str, description: str, req_fields: str, opt_fields: str, example: str):
        """Displays a formatted panel for TASK actions before prompting for input."""
        print("\n\033[1;35m" + "═" * 60 + "\033[0m")
        print(f" \033[1;36m{task_name}\033[0m")
        print(f" {description}")
        print("\033[1;35m" + "─" * 60 + "\033[0m")
        print(f" \033[1mRequired:\033[0m {req_fields}")
        print(f" \033[1mOptional:\033[0m {opt_fields}")
        print("\n \033[1mExample Payload:\033[0m")
        print(f" \033[36m{example}\033[0m")
        print("\033[1;35m" + "═" * 60 + "\033[0m\n")

    # ==========================
    # Task Execution & Artifacts
    # ==========================
    def _exec_task(self, action_name: str, opcode: int, **kwargs):
        try:
            result = self._execute_and_remember(action_name, opcode, **kwargs)
            if not result: return
            
            if result.status < 300:
                print("✅ Task Successful!")
                self._handle_result_data(result.data)
            else:
                print(f"❌ Task Failed: {result.status} - {result.error}")
            
        except Exception as e:
            print(f"❌ Execution Error: {e}")

    def _handle_result_data(self, data: dict):
        # 1. Check for Artifact (Strict Contract)
        # Structure: {..., "data": { "artifact_path": "..." } }
        inner_data = data.get("data", {}) if isinstance(data, dict) else {}
        artifact_path = inner_data.get("artifact_path")
        
        if artifact_path:
            print(f"\n⚠️  Result too large. Artifact generated at server: {artifact_path}")
            print("⬇️  Auto-downloading...")
            self._trigger_artifact_download(artifact_path)
            return

        # 2. Check for Inline Output
        output = inner_data.get("output")
        if output:
            print("\n--- Result Output ---")
            print(output)
            print("---------------------")
        else:
            # Generic Dump
            print(f"\nResult: {data}")

    def _trigger_artifact_download(self, artifact_path: str):
        try:
             # Use execute(OP_GET)
             res = self.state.agent_client.execute(OP_GET, filename=artifact_path)
             if res.status >= 300:
                  print(f"❌ Artifact Download Failed: {res.status} {res.error}")
                  return
             
             content = res.data

             # Save
             local_name = f"downloaded_{os.path.basename(artifact_path)}"
             local_path = os.path.join(self.state.download_dir, local_name)
             
             with open(local_path, "wb") as f:
                 f.write(content)
                 
             print(f"✅ Downloaded Artifact: {local_path}")
             self._preview_content(content)
             
        except Exception as e:
            print(f"❌ Artifact Download Failed: {e}")

    def _preview_content(self, content: bytes, max_lines=20):
        try:
            text = content.decode('utf-8')
            lines = text.splitlines()
            print("\n--- Preview ---")
            for line in lines[:max_lines]:
                print(line)
            if len(lines) > max_lines:
                print(f"... ({len(lines) - max_lines} more lines)")
            print("---------------")
        except UnicodeDecodeError:
            print("[Binary Content - No Preview]")


