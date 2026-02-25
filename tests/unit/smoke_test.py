from client.dhcp_client import DHCPClient
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        client = DHCPClient(mac_address="00:11:22:33:44:55")
        print(f"Client initialized: {client.mac_address}")
        print(f"Initial state: {client.state}")
        print("Success")
    except Exception as e:
        print(f"Failed: {e}")
