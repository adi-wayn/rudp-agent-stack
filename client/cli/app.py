import os
from client.cli.state import SessionState
from client.cli.ui import print_banner, print_header, print_menu, print_help_panel
from client.cli.actions.network import action_dhcp, action_dns, action_connect, action_disconnect
from client.cli.actions.file_ops import action_list, action_get, action_append, action_upload
from client.cli.actions.tasks import action_task_search, action_task_filter, action_task_hash, action_replay
from client.cli.ui import preview_content

class InteractiveCLI:
    """Main CLI Controller orchestrating the modular actions."""
    def __init__(self, failure_engine=None):
        self.state = SessionState()
        self.state.failure_engine = failure_engine
        self.running = True
        
        if not os.path.exists(self.state.download_dir):
            os.makedirs(self.state.download_dir)

    def start(self):
        """Main Loop."""
        print_banner()
        while self.running:
            print_header(self.state)
            print_menu()
            choice = input("\nSelect an option (0-13): ").strip()
            try:
                self._handle_choice(choice)
            except Exception as e:
                print(f"\n❌ \033[31mError:\033[0m {e}")
                input("Press Enter to continue...")

    def _execute_and_remember(self, action_name: str, opcode: int, **kwargs):
        """
        Centralized core execution for the CLI.
        Forces explicit generation of request_id_override to store it for replays.
        """
        req_id = kwargs.get("request_id_override")
        if not req_id:
            req_id = self.state.agent_client.request_id_manager.next_id()
            kwargs["request_id_override"] = req_id
            
            self.state.last_action_name = action_name
            self.state.last_opcode = opcode
            self.state.last_kwargs = kwargs.copy()
            self.state.last_request_id = req_id

        print(f"\n⏳ \033[36mExecuting '{action_name}' (ReqID: {req_id})...\033[0m")
        try:
            return self.state.agent_client.execute(opcode, **kwargs)
        except Exception as e:
            print(f"❌ \033[31mExecution Error:\033[0m {e}")
            return None

    def _handle_choice(self, choice: str):
        if choice == "0":
            self.running = False
            print("Goodbye!")
            return
            
        map_action = {
            "1": lambda: action_dhcp(self.state),
            "2": lambda: action_dns(self.state),
            "3": lambda: action_connect(self.state),
            "4": lambda: action_disconnect(self.state),
            "5": lambda: action_list(self.state, self._execute_and_remember),
            "6": lambda: action_get(self.state, self._execute_and_remember, preview_content),
            "7": lambda: action_append(self.state, self._execute_and_remember),
            "8": lambda: action_upload(self.state, self._execute_and_remember),
            "9": lambda: action_task_search(self.state, self._execute_and_remember),
            "10": lambda: action_task_filter(self.state, self._execute_and_remember),
            "11": lambda: action_task_hash(self.state, self._execute_and_remember),
            "12": lambda: action_replay(self.state, self._execute_and_remember),
            "13": print_help_panel
        }
        
        action = map_action.get(choice)
        if action:
            action()
        else:
            print("\033[31mInvalid choice.\033[0m")
