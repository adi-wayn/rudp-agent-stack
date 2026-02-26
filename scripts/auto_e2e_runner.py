#!/usr/bin/env python3
import threading
import time
import os
import secrets
import logging
from typing import Optional

from server.dhcp_server import DHCPServer
from server.dns_server import DoHRUDPServer
from server.agent_server import AgentServer
from server.transport.rudp_server import RUDPServerTransport

from client.dhcp_client import DHCPClient
from client.dns_client import DNSClient
from client.agent_client import AgentClient
from client.transport.rudp_client import RUDPClientTransport
from simulations.failure_engine import FailureEngine
from common.constants import OP_LIST, OP_GET, OP_UPLOAD, OP_TASK_HASH_AND_STORE

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("AutoE2ERunner")

# --- Configuration ---
DHCP_S_PORT = 6767
DHCP_C_PORT = 6868
DNS_PORT = 8054
APP_PORT = 8081

SERVER_ROOT = "/tmp/e2e_test_sandbox"
CLIENT_ROOT = "/tmp/e2e_test_client_home"
TEST_FILE_SIZE = 50 * 1024  # 50KB

def setup_directories():
    os.makedirs(SERVER_ROOT, exist_ok=True)
    os.makedirs(CLIENT_ROOT, exist_ok=True)
    test_filepath = os.path.join(CLIENT_ROOT, "stress_test.bin")
    with open(test_filepath, "wb") as f:
        f.write(secrets.token_bytes(TEST_FILE_SIZE))
    return test_filepath

def run_servers():
    logger.info("Starting Servers in background...")
    
    # DHCP Server
    dhcp_server = DHCPServer(port=DHCP_S_PORT, client_port=DHCP_C_PORT)
    t_dhcp = threading.Thread(target=dhcp_server.start, daemon=True)
    t_dhcp.start()
    
    # DNS Server
    dns_server = DoHRUDPServer(port=DNS_PORT)
    t_dns = threading.Thread(target=dns_server.start, daemon=True)
    t_dns.start()
    
    # App Server over RUDP
    transport = RUDPServerTransport(port=APP_PORT, bind_ip="127.0.0.1")
    agent_server = AgentServer(sandbox_root=SERVER_ROOT, transport=transport)
    t_app = threading.Thread(target=agent_server.run, daemon=True)
    t_app.start()
    
    time.sleep(1) # Give servers time to bind
    return dhcp_server, dns_server, agent_server

def main():
    test_filepath = setup_directories()
    servers = run_servers()
    
    logger.info("=== Phase 1: DHCP ===")
    dhcp_client = DHCPClient(mac_address="00:1A:2B:3C:4D:5E", server_port=DHCP_S_PORT, client_port=DHCP_C_PORT)
    success = dhcp_client.acquire_lease()
    assert success, "DHCP lease acquisition failed"
    dhcp_ip = dhcp_client.assigned_ip
    logger.info(f"DHCP Success! IP assigned: {dhcp_ip}")
    
    logger.info("\n=== Phase 2: DNS ===")
    # DHCPServer uses loopback IP for virtual distribution by default usually
    dns_client = DNSClient(dns_server_ip="127.0.0.1", client_ip=dhcp_ip, port=DNS_PORT)
    resolved_ip = dns_client.resolve("agent.local")
    assert resolved_ip == "127.0.0.1", f"DNS Resolution failed or unexpected IP: {resolved_ip}"
    logger.info(f"DNS Resolution Success! agent.local -> {resolved_ip}")
    
    logger.info("\n=== Phase 3: Application Stress Test (20% Loss) ===")
    failure_engine = FailureEngine(drop_rate=0.20, latency_ms=10)
    logger.info("Injected FailureEngine with 20% drop rate.")
    
    app_transport = RUDPClientTransport(
        server_host=resolved_ip, 
        server_port=APP_PORT, 
        client_ip=dhcp_ip, 
        failure_engine=failure_engine
    )
    app_transport.start()
    
    app_client = AgentClient(transport=app_transport)
    
    try:
        # Step 1: Upload Large File
        logger.info(f"--- Action: UPLOAD ({TEST_FILE_SIZE} bytes) ---")
        remote_name = "stress_test.bin"
        res = app_client.execute(OP_UPLOAD, local_path=test_filepath, remote_name=remote_name)
        assert res.error is None, f"Upload failed: {res.error}"
        logger.info("UPLOAD completed.")
        
        # Step 2: Task Execution (Hash File)
        logger.info("--- Action: TASK HASH ---")
        # Ensure we send the correct syntax
        task_res = app_client.execute(OP_TASK_HASH_AND_STORE, input_file=remote_name, out_file=remote_name + ".sha256")
        assert task_res.error is None, f"Task Hash failed: {task_res.error}"
        print(f"Task Output: {task_res.data}")
        original_hash = ""
        # The output usually contains the hash if you parse it, but for now we just assert 200.
        logger.info("TASK HASH completed.")
        
        # Step 3: Download File
        logger.info("--- Action: GET (Download) ---")
        download_path = os.path.join(CLIENT_ROOT, "downloaded_stress.bin")
        get_res = app_client.execute(OP_GET, filename=remote_name)
        assert get_res.error is None, f"GET failed: {get_res.error}"
        downloaded_bytes = get_res.data
        if not downloaded_bytes:
            assert False, "GET returned empty data"
        
        with open(download_path, "wb") as f:
            f.write(downloaded_bytes)
        logger.info("GET completed.")
        
        # Verify byte-for-byte match
        with open(test_filepath, "rb") as f1, open(download_path, "rb") as f2:
            sent_bytes = f1.read()
            rec_bytes = f2.read()
            assert sent_bytes == rec_bytes, "Data corrupted! Downloaded bytes do not match original."
        logger.info("DATA MATCH: Downloaded file matches exactly.")
        
        # Step 4: LIST
        logger.info("--- Action: LIST ---")
        list_res = app_client.execute(OP_LIST)
        assert list_res.error is None, f"List failed: {list_res.error}"
        logger.info(f"LIST output: {list_res.data}")
        
        logger.info("\n=== SUCCESS: All Phases Passed! STRESS TEST COMPLETE. ===")
    finally:
        app_client.close()

if __name__ == "__main__":
    main()
