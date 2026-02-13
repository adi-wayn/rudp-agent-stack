"""
Day 2 Server Runner.
Wires TCP connection handling to AgentServer pipeline.
For verification purposes only.
"""
import socket
import logging
import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

from common.constants import AGENT_SERVER_PORT, LOOPBACK_IP
from server.agent_server import AgentServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Day2Server")

def run():
    sandbox_dir = "./sandbox"
    agent = AgentServer(sandbox_root=sandbox_dir)
    
    # Create valid files in sandbox for LIST test
    os.makedirs(sandbox_dir, exist_ok=True)
    with open(os.path.join(sandbox_dir, "hello.txt"), "w") as f:
        f.write("Hello Day 2")
        
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((LOOPBACK_IP, AGENT_SERVER_PORT))
    sock.listen(1)
    
    logger.info(f"Day 2 Agent Server listening on {LOOPBACK_IP}:{AGENT_SERVER_PORT}")
    
    try:
        while True:
            conn, addr = sock.accept()
            logger.info(f"Connected: {addr}")
            try:
                while True:
                    # Simple framing for demo: read header then payload
                    # But AgentServer.process_request expects FULL message.
                    # So we read header first to get len, then read payload, then verify.
                    
                    data = conn.recv(1024) # Naive read
                    if not data:
                        break
                        
                    response = agent.process_request(str(addr), data)
                    if response:
                        conn.sendall(response)
                        
            except Exception as e:
                logger.error(f"Connection error: {e}")
            finally:
                conn.close()
    except KeyboardInterrupt:
        logger.info("Stopping")
    finally:
        sock.close()

if __name__ == "__main__":
    run()
