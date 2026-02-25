import dataclasses
from typing import Optional, Any
from client.agent_client import AgentClient

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
    failure_engine: Optional[Any] = None
    
    # Replay State
    last_action_name: Optional[str] = None
    last_opcode: Optional[int] = None
    last_kwargs: Optional[dict] = None
    last_request_id: Optional[int] = None
