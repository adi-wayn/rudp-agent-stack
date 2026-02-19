import sys
import logging
from client.agent_client import AgentClient
from common.constants import OP_LIST, LOOPBACK_IP, AGENT_SERVER_PORT

# Configure basic logging for the client run
logging.basicConfig(
    level=logging.INFO,
    format="[Client] %(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ClientMain")

def main():
    """
    Main entry point for the Day-2 Client.
    Executes a simple LIST request flow.
    """
    logger.info("Starting Day-2 Client...")

    client = None
    try:
        # 1. Instantiate Agent Client
        client = AgentClient()
        
        # 2. Send LIST Request (Opcode 0x05)
        logger.info(f"Sending LIST request to {LOOPBACK_IP}:{AGENT_SERVER_PORT}")
        result = client.execute(OP_LIST)
        
        # 3. Print Response
        print("\n--- Server Response ---")
        print(f"Status: {result.status}")
        print(f"Error:  {result.error}")
        print(f"Data:   {result.data}")
        print("-----------------------\n")
        
    except Exception as e:
        logger.error(f"Client execution failed: {e}")
        sys.exit(1)
    finally:
        # 4. Cleanup
        if client:
            client.close()
        logger.info("Client finished.")

if __name__ == "__main__":
    main()
