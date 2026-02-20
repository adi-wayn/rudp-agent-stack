from client.dhcp_client import DHCPClient
from client.dns_client import DNSClient
from client.transport.factory import TransportFactory
from client.agent_client import AgentClient
from common.constants import INITIAL_RTO
from client.cli.prompts import prompt_text, prompt_yes_no

def action_dhcp(state):
    print("\n[DHCP] Discovering...")
    client = DHCPClient()
    try:
        client.discover()
        print("✅ DHCP Success (Mocked/Real?)") 
    except NotImplementedError:
         print("⚠️  DHCP Not Implemented yet.")
    except Exception as e:
         print(f"❌ DHCP Failed: {e}")

def action_dns(state):
    print("\n[DNS] Resolving 'app.server'...")
    dns_ip = prompt_text("Enter DNS Server IP", default="127.0.0.1", required=True)
    client = DNSClient(dns_ip)
    try:
        resolved = client.resolve("app.server")
        if resolved:
            state.server_ip = resolved
            print(f"✅ Resolved app.server -> {resolved}")
        else:
            print("❌ DNS Resolution failed.")
    except NotImplementedError:
         print("⚠️  DNS Not Implemented yet.")
    except Exception as e:
         print(f"❌ DNS Failed: {e}")

def action_connect(state):
    if state.server_ip == "NOT_SET":
         print("⚠️  Please resolve Server IP (DNS) first (or manually set).")
         if prompt_yes_no("Set Server IP manually?", default="N"):
             state.server_ip = prompt_text("Server IP", required=True)
         else:
             return

    mode = prompt_text("Transport Mode (TCP/RUDP)", default=state.transport_mode)
    state.transport_mode = mode.upper()
    
    print(f"Connecting to {state.server_ip}:{state.server_port} via {state.transport_mode}...")
    
    try:
        transport = TransportFactory.create(
            state.transport_mode, 
            state.server_ip, 
            state.server_port
        )
        state.agent_client = AgentClient(transport)
        state.agent_client.transport.connect(timeout=INITIAL_RTO)
        
        state.is_connected = True
        print("✅ \033[32mConnected!\033[0m")
        
    except Exception as e:
        print(f"❌ \033[31mConnection Failed:\033[0m {e}")
        state.is_connected = False
        state.agent_client = None

def action_disconnect(state):
    if state.agent_client:
        state.agent_client.close()
    state.is_connected = False
    state.agent_client = None
    print("Disconnected.")
