"""
Client Entry Point.
Launches the Interactive CLI.
"""
from client.cli.interactive_menu import InteractiveCLI

def main():
    cli = InteractiveCLI()
    try:
        cli.start()
    except KeyboardInterrupt:
        print("\nExiting...")

if __name__ == "__main__":
    main()
