#!/usr/bin/env python3
import threading
import time
import os
import secrets
import logging

from server.dhcp_server import DHCPServer
from server.dns_server import DoHRUDPServer
from server.agent_server import AgentServer
from server.transport.rudp_server import RUDPServerTransport

from client.dhcp_client import DHCPClient
from client.dns_client import DNSClient
from client.agent_client import AgentClient
from client.transport.rudp_client import RUDPClientTransport

from common.constants import OP_GET, OP_UPLOAD

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("StreamingTest")

# --- Configuration ---
DHCP_S_PORT = 6767
DHCP_C_PORT = 6868
DNS_PORT = 8054
APP_PORT = 8081

SERVER_ROOT = "/tmp/streaming_test_sandbox"
CLIENT_ROOT = "/tmp/streaming_test_client_home"
TEST_FILE_SIZE = 350 * 1024  # 350KB -> greater than 256KB triggers streaming rules

def setup_directories():
    os.makedirs(SERVER_ROOT, exist_ok=True)
    os.makedirs(CLIENT_ROOT, exist_ok=True)
    
    test_filepath = os.path.join(CLIENT_ROOT, "large_350kb.dat")
    with open(test_filepath, "wb") as f:
        f.write(secrets.token_bytes(TEST_FILE_SIZE))
        
    return test_filepath

def run_servers():
    logger.info("Starting Servers in background...")
    
    dhcp_server = DHCPServer(port=DHCP_S_PORT, client_port=DHCP_C_PORT)
    t_dhcp = threading.Thread(target=dhcp_server.start, daemon=True)
    t_dhcp.start()
    
    dns_server = DoHRUDPServer(port=DNS_PORT)
    t_dns = threading.Thread(target=dns_server.start, daemon=True)
    t_dns.start()
    
    transport = RUDPServerTransport(port=APP_PORT, bind_ip="127.0.0.1")
    agent_server = AgentServer(sandbox_root=SERVER_ROOT, transport=transport)
    t_app = threading.Thread(target=agent_server.run, daemon=True)
    t_app.start()
    
    time.sleep(1)
    return dhcp_server, dns_server, agent_server

def main():
    test_filepath = setup_directories()
    servers = run_servers()
    
    # Phase 1: DHCP
    logger.info("=== Phase 1: DHCP ===")
    dhcp_client = DHCPClient(mac_address="00:1A:2B:3C:4D:5E", server_port=DHCP_S_PORT, client_port=DHCP_C_PORT)
    assert dhcp_client.acquire_lease(), "DHCP lease acquisition failed"
    dhcp_ip = dhcp_client.assigned_ip
    logger.info(f"DHCP Success! IP assigned: {dhcp_ip}")
    
    # Phase 2: DNS
    logger.info("\n=== Phase 2: DNS ===")
    dns_client = DNSClient(dns_server_ip="127.0.0.1", client_ip=dhcp_ip, port=DNS_PORT)
    resolved_ip = dns_client.resolve("agent.local")
    assert resolved_ip == "127.0.0.1", "DNS Resolution failed"
    logger.info(f"DNS Resolution Success! agent.local -> {resolved_ip}")
    
    # Phase 3: Application > 256KB Streaming Test
    logger.info(f"\n=== Phase 3: Streaming Execution Test (> 256KB) ===")
    logger.info("Note: Using perfect network conditions (0% loss) to specifically test App Layer.")
    
    # Passing None for failure_engine -> PERFECT network
    app_transport = RUDPClientTransport(
        server_host=resolved_ip, 
        server_port=APP_PORT, 
        client_ip=dhcp_ip
    )
    app_transport.start()
    app_client = AgentClient(transport=app_transport)
    
    remote_name = "large_350kb.dat"
    download_path = os.path.join(CLIENT_ROOT, "downloaded_large_350kb.dat")
    
    try:
        # Step 1: Upload Large File (Triggers Streaming)
        logger.info(f"--- Action: UPLOAD ({TEST_FILE_SIZE} bytes) ---")
        res = app_client.execute(OP_UPLOAD, local_path=test_filepath, remote_name=remote_name)
        assert res.error is None, f"Upload failed: {res.error}"
        logger.info("UPLOAD completed.")
        
        # Step 2: Download Large File (Triggers chunked delivery mapping)
        logger.info(f"--- Action: GET ({TEST_FILE_SIZE} bytes) ---")
        get_res = app_client.execute(OP_GET, filename=remote_name)
        assert get_res.error is None, f"GET failed: {get_res.error}"
        
        with open(download_path, "wb") as f:
            f.write(get_res.data)
        logger.info("GET completed.")
        
        # Validation
        with open(test_filepath, "rb") as f1, open(download_path, "rb") as f2:
            orig = f1.read()
            dl = f2.read()
            assert orig == dl, "Data corrupted! Streaming upload/download failed to maintain integrity."
            
        logger.info("\n###################################################################")
        logger.info("### STREAMING BENCHMARK PASSED (350KB transferred successfully) ###")
        logger.info("###################################################################")
        
    finally:
        app_client.close()

if __name__ == "__main__":
    main()
