import os
import sys

print(f"CWD: {os.getcwd()}")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not Set')}")

try:
    import client.agent.upload_client
    print("SUCCESS: Imported client.agent.upload_client")
except ImportError as e:
    print(f"FAILURE: Could not import client.agent.upload_client: {e}")

try:
    import server.agent.upload_session
    print("SUCCESS: Imported server.agent.upload_session")
except ImportError as e:
    print(f"FAILURE: Could not import server.agent.upload_session: {e}")
