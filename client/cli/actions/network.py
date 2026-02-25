import random
import platform
import subprocess
from client.dhcp_client import DHCPClient
from client.dns_client import DNSClient
from client.transport.factory import TransportFactory
from client.agent_client import AgentClient
from common.constants import INITIAL_RTO
from client.cli.prompts import prompt_text, prompt_yes_no

def _generate_random_mac() -> str:
    return ":".join([f"{random.randint(0, 255):02X}" for _ in range(6)])

def action_dhcp(state):
    print("\n[DHCP] Discovering...")
    mac = _generate_random_mac()
    client = DHCPClient(mac_address=mac)
    try:
        if client.acquire_lease():
            state.client_ip = client.assigned_ip
            print(f"✅ DHCP Success. Client IP: {state.client_ip}") 
            
            # --- OS Workaround for macOS loopback binding ---
            if platform.system() == "Darwin" and state.client_ip not in ["NOT_SET", "127.0.0.1"]:
                try:
                    subprocess.run(["ifconfig", "lo0", "alias", state.client_ip, "up"], capture_output=True, check=True)
                    print(f"[INFO] macOS detected. Dynamically aliased {state.client_ip} to lo0 interface to allow explicit socket binding.")
                except Exception as e:
                    print(f"⚠️  Failed to alias IP on macOS. Binding may fail: {e}")
        else:
            print("❌ DHCP Failed to acquire lease.")
    except NotImplementedError:
         print("⚠️  DHCP Not Implemented yet.")
    except Exception as e:
         print(f"❌ DHCP Failed: Timeout or Server down? Details: {e}")

def action_dns(state):
    print("\n[DNS] Resolving 'agent.local'...")
    dns_ip = prompt_text("Enter DNS Server IP", default="127.0.0.1", required=True)
    
    # Check if we have an assigned IP from DHCP to bind to. NOT_SET is handled gracefully by DNSClient.
    client = DNSClient(dns_server_ip=dns_ip, client_ip=state.client_ip)
    
    try:
        resolved = client.resolve("agent.local")
        if resolved:
            state.server_ip = resolved
            print(f"✅ Resolved agent.local -> {resolved}")
        else:
            print("❌ DNS Resolution failed.")
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
            state.server_port,
            client_ip=state.client_ip,
            failure_engine=state.failure_engine
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
