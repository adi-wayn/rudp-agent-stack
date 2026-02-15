import sys
import logging
from server.agent_server import AgentServer

# Configure basic logging for the server run
# Mirrors client/__main__.py style
logging.basicConfig(
    level=logging.INFO,
    format="[Server] %(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ServerMain")

def main():
    """
    Main entry point for the Application Server.
    Instantiates AgentServer (which owns the Transport) and starts it.
    """
    logger.info("Starting Production Server...")
    
    # Instantiate the Real Application Server
    # Using a default relative path 'sandbox' for production run
    sandbox_dir = "./sandbox"
    
    # AgentServer now defaults to owning a TCPServerTransport
    agent = AgentServer(sandbox_root=sandbox_dir)
    
    try:
        # AgentServer drives the execution loop
        agent.run()
    except Exception as e:
        logger.critical(f"Server execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
