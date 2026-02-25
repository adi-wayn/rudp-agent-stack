import sys
import argparse
import logging
from server.agent_server import AgentServer
from server.transport.tcp_server import TCPServerTransport
from server.transport.rudp_server import RUDPServerTransport
from simulations.failure_engine import FailureEngine

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
    
    parser = argparse.ArgumentParser(description="Agent-based Application Server")
    parser.add_argument("--RUDP", action="store_true", help="Start server in Reliable UDP mode")
    parser.add_argument("--loss", type=int, default=0, help="Packet drop percentage (0-100)")
    parser.add_argument("--latency", type=int, default=0, help="Latency injection in ms")
    parser.add_argument("--dup", type=int, default=0, help="Packet duplication percentage (0-100)")
    args = parser.parse_args()
    
    # Instantiate the Real Application Server
    # Using a default relative path 'sandbox' for production run
    sandbox_dir = "./sandbox"
    
    failure_engine = None
    if args.loss > 0 or args.latency > 0 or args.dup > 0:
        failure_engine = FailureEngine(drop_rate=args.loss/100.0, latency_ms=args.latency, dup_rate=args.dup/100.0)

    # Instantiate appropriate transport based on CLI flag
    transport = RUDPServerTransport(failure_engine=failure_engine) if args.RUDP else TCPServerTransport()
    
    # AgentServer now owns the polymorphic transport
    agent = AgentServer(sandbox_root=sandbox_dir, transport=transport)
    
    try:
        # AgentServer drives the execution loop
        agent.run()
    except Exception as e:
        logger.critical(f"Server execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
