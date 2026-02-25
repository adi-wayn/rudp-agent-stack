import sys
import argparse
import logging
import threading
import os
from server.agent_server import AgentServer
from server.transport.tcp_server import TCPServerTransport
from server.transport.rudp_server import RUDPServerTransport
from simulations.failure_engine import FailureEngine
from server.dhcp_server import DHCPServer
from server.dns_server import DoHRUDPServer

# Configure basic logging for the server run
# Mirrors client/__main__.py style
logging.basicConfig(
    level=logging.INFO,
    format="[Server] %(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ServerMain")

def start_dhcp_server():
    """Helper function to start the DHCP Server in a separate thread."""
    server = DHCPServer()
    try:
        server.start()
    except PermissionError as e:
        if e.errno == 13:
            logger.critical("CRITICAL: Binding to port 67 requires elevated privileges. Please run with sudo: sudo python3 -m server --all")
            # Force exit since we are in a daemon thread and want to immediately shutdown the orchestrator
            os._exit(1)
        else:
            logger.critical(f"DHCP Server encountered a PermissionError: {e}")
            os._exit(1)
    except Exception as e:
        logger.critical(f"DHCP Server execution failed: {e}")
        os._exit(1)

def start_dns_server():
    """Helper function to start the DNS Server in a separate thread."""
    server = DoHRUDPServer()
    try:
        server.start()
    except Exception as e:
        logger.critical(f"DNS Server execution failed: {e}")
        os._exit(1)

def main():
    """
    Main entry point for the Application Server Orchestrator.
    Manages isolated servers (Agent, DHCP, DNS) based on run configurations.
    """
    logger.info("Starting Production Server Orchestrator...")
    
    parser = argparse.ArgumentParser(description="Agent-based Application Server Orchestrator")
    parser.add_argument("--RUDP", action="store_true", help="Start Agent server in Reliable UDP mode")
    parser.add_argument("--loss", type=int, default=0, help="Packet drop percentage (0-100)")
    parser.add_argument("--latency", type=int, default=0, help="Latency injection in ms")
    parser.add_argument("--dup", type=int, default=0, help="Packet duplication percentage (0-100)")
    
    # Mutually exclusive group for execution modes
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="Start AgentServer, DHCPServer, and DNSServer concurrently (Default)")
    group.add_argument("--dhcp-only", action="store_true", help="Start ONLY the DHCP Server")
    group.add_argument("--dns-only", action="store_true", help="Start ONLY the DNS Server")
    group.add_argument("--agent-only", action="store_true", help="Start ONLY the Agent Server")
    
    args = parser.parse_args()
    
    # Set default to --all if nothing is provided
    if not (args.all or args.dhcp_only or args.agent_only or args.dns_only):
        args.all = True
        
    # Start DHCP Server Flow (daemon)
    if args.all or args.dhcp_only:
        logger.info("Spawning DHCPServer in background thread...")
        dhcp_thread = threading.Thread(target=start_dhcp_server, daemon=True)
        dhcp_thread.start()
        
        # If we ONLY want DHCP, we block the main thread from exiting immediately
        if args.dhcp_only:
            try:
                dhcp_thread.join()
            except KeyboardInterrupt:
                logger.info("Shutting down orchestrator...")
            sys.exit(0)

    # Start DNS Server Flow (daemon)
    if args.all or args.dns_only:
        logger.info("Spawning DNSServer in background thread...")
        dns_thread = threading.Thread(target=start_dns_server, daemon=True)
        dns_thread.start()
        
        # If we ONLY want DNS, we block the main thread from exiting immediately
        if args.dns_only:
            try:
                dns_thread.join()
            except KeyboardInterrupt:
                logger.info("Shutting down orchestrator...")
            sys.exit(0)

    # Start Agent Server Flow (Main Thread)
    if args.all or args.agent_only:
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
            # AgentServer drives the execution loop blockingly
            agent.run()
        except KeyboardInterrupt:
            logger.info("Shutting down orchestrator...")
        except Exception as e:
            logger.critical(f"Agent Server execution failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
