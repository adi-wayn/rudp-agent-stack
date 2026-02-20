"""
E2E Test for Interactive CLI Replay (Idempotency) Feature.
Spawns a real AgentServer in a thread and tests the InteractiveCLI flow.
"""
import os
import time
import threading
import unittest
import io
from unittest.mock import patch

from server.agent_server import AgentServer
from client.cli.interactive_menu import InteractiveCLI

class TestCLIReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Setup clean sandbox
        cls.sandbox_dir = "./test_sandbox"
        if not os.path.exists(cls.sandbox_dir):
            os.makedirs(cls.sandbox_dir)
            
        cls.test_file = os.path.join(cls.sandbox_dir, "test_replay.txt")
        with open(cls.test_file, "w") as f:
            f.write("INITIAL\n")
            
        from server.transport.tcp_server import TCPServerTransport
        transport = TCPServerTransport(bind_ip="127.0.0.1", port=8081)
        cls.server = AgentServer(sandbox_root=cls.sandbox_dir, transport=transport)
        cls.server_thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.server_thread.start()
        
        # Give server time to bind
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.server.transport.close()
        except:
            pass
        cls.server_thread.join(timeout=1)
        if os.path.exists(cls.test_file):
            os.remove(cls.test_file)
        if os.path.exists(cls.sandbox_dir):
            os.rmdir(cls.sandbox_dir)

    @patch('builtins.input')
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_replay_append_idempotent(self, mock_stdout, mock_input):
        """
        1. Connect
        2. APPEND "LINE1" to test_replay.txt
        3. Replay (Option 12)
        4. Verify file was NOT appended twice.
        """
        # Inputs:
        # 3 (Connect), y (manual IP), 127.0.0.1, TCP (port is hardcoded to 8080 usually in CLI state! Wait)
        # Ah, we can't easily change port in CLI standard connect flow without modifying state manually before start!
        # Let's override state manually before calling start()
        pass

    def run_cli_flow(self):
        # We instead build a sequence for the CLI.
        # But wait, InteractiveCLI default port is 8080.
        cli = InteractiveCLI()
        cli.state.server_port = 8081 # override port for this test
        
        with patch('builtins.input') as mock_input:
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                
                # Sequence:
                # Menu -> 3 (Connect)
                #   -> manual IP? 'y'
                #   -> IP '127.0.0.1'
                #   -> Transport 'TCP'
                # Menu -> 7 (Append)
                #   -> filename: 'test_replay.txt'
                #   -> data: 'LINE1'
                # Menu -> 12 (Replay)
                # Menu -> 0 (Exit)
                
                mock_input.side_effect = [
                    "3", "y", "127.0.0.1", "TCP",
                    "7", "test_replay.txt", "LINE1",
                    "12",
                    "0"
                ]
                
                cli.start()
                
                output = mock_stdout.getvalue()
                return output

    def test_idempotent_replay(self):
        output = self.run_cli_flow()
        
        # Verify Server Success
        self.assertIn("✅ Connected!", output)
        self.assertIn("✅ Append Success", output)
        
        # Verify Replay Print
        self.assertIn("[REPLAY] Replaying Last Request", output)
        self.assertIn("Replay Success", output)
        
        # Verify File Content
        with open(self.test_file, "r") as f:
            content = f.read()
            
        # It should contain exactly one "LINE1", proving the second APPEND was caught by idempotency cache.
        self.assertEqual(content, "INITIAL\nLINE1")

if __name__ == "__main__":
    unittest.main()
