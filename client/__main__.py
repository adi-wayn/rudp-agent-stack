"""
Client Entry Point.
Launches the Interactive CLI.
"""
import argparse
from client.cli.app import InteractiveCLI
from simulations.failure_engine import FailureEngine

def main():
    parser = argparse.ArgumentParser(description="Agent-based Client CLI")
    parser.add_argument("--loss", type=int, default=0, help="Packet drop percentage (0-100)")
    parser.add_argument("--latency", type=int, default=0, help="Latency injection in ms")
    parser.add_argument("--dup", type=int, default=0, help="Packet duplication percentage (0-100)")
    args = parser.parse_args()

    failure_engine = None
    if args.loss > 0 or args.latency > 0 or args.dup > 0:
        failure_engine = FailureEngine(drop_rate=args.loss/100.0, latency_ms=args.latency, dup_rate=args.dup/100.0)

    cli = InteractiveCLI(failure_engine=failure_engine)
    try:
        cli.start()
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()
