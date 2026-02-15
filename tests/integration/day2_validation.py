"""
Day-2 Client Validation Script.
Verifies:
1. Connection establishment
2. Envelope construction (LIST opcode)
3. Strict Response Framing
4. Request ID Validation
5. Status Code Parsing
"""
import logging
import sys
import time
from client.agent_client import AgentClient
from common.constants import OP_LIST, LOOPBACK_IP, AGENT_SERVER_PORT

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="[Validation] %(asctime)s - %(levelname)s - %(message)s",
    filename='client_validation.log',
    filemode='w'
)
# Add console handler
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)
logger = logging.getLogger("Day2Validation")

def test_list_happy_path():
    """
    Test a valid LIST request.
    """
    logger.info("--- Starting LIST Happy Path Test ---")
    client = AgentClient(LOOPBACK_IP, AGENT_SERVER_PORT)
    
    try:
        # Send LIST with empty filter
        response = client.send_request(OP_LIST, {})
        
        # Validation 1: Status Code
        status = response.get("status")
        if status != 200:
            logger.error(f"FAILED: Expected status 200, got {status}")
            sys.exit(1)
            
        # Validation 2: Data presence
        if "data" not in response:
             logger.error("FAILED: Response missing 'data' field")
             sys.exit(1)
             
        logger.info("SUCCESS: LIST returned 200 OK and valid structure.")
        logger.info(f"Response Payload: {response}")

    except Exception as e:
        logger.error(f"CRITICAL FAILURE: {e}")
        sys.exit(1)
    finally:
        client.close()

def main():
    logger.info("Running Day-2 validation suite...")
    
    # 1. Happy Path
    test_list_happy_path()
    
    # TODO: Add negative tests/fault injection if infrastructure allows
    # For Day-2, proof-of-life is the primary goal.

if __name__ == "__main__":
    main()
