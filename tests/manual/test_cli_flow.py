"""
Manual/Simulated Verification of Interactive CLI.
Pipes inputs to the CLI loop to verify flow logic.
"""
import sys
import io
import unittest
from unittest.mock import MagicMock, patch
from client.cli.interactive_menu import InteractiveCLI
from common.constants import OP_GET, OP_TASK_SEARCH_REPORT

class TestCLIFlow(unittest.TestCase):
    
    @patch('builtins.input')
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_basic_flow_no_server(self, mock_stdout, mock_input):
        """
        Simulate:
        1. Start
        2. DHCP (Fail/NotImpl)
        3. DNS (NotImpl)
        4. Connect (Simulate Fail)
        5. Exit
        """
        # Define Input Sequence
        mock_input.side_effect = [
            "1", # DHCP
            "2", # DNS
            "127.0.0.1", # DNS IP Prompt
            "3", # Connect
            "N", # Connect Manual IP -> No
            "0", # Exit
        ]
        
        cli = InteractiveCLI()
        cli.start()
        
        output = mock_stdout.getvalue()
        
        # Assertions
        assert "RUDP AGENT CLIENT" in output
        assert "DHCP: Acquire IP" in output
        assert "DHCP Success" in output or "Not Implemented" in output or "DHCP Failed" in output
        assert "DNS Not Implemented" in output or "DNS Failed" in output
        assert "Goodbye!" in output

    @patch('builtins.input')
    @patch('sys.stdout', new_callable=io.StringIO)
    @patch('client.cli.interactive_menu.TransportFactory.create')
    def test_artifact_flow(self, mock_create_transport, mock_stdout, mock_input):
        """
        Simulate Artifact Auto-Download Flow.
        1. Connect (Mock Success)
        2. Run Task (Mock Artifact Response)
        3. Trigger Auto Download (Mock GET)
        4. Exit
        """
        # Mock Transport
        mock_transport = MagicMock()
        mock_create_transport.return_value = mock_transport
        
        # Mock Client Instance & Execute
        mock_client_instance = MagicMock()
        mock_client_instance.transport = mock_transport
        
        # Mock Task Response (Artifact)
        mock_task_res = MagicMock()
        mock_task_res.status = 200
        mock_task_res.data = {
            "data": { "artifact_path": "artifacts/test_result.txt" }
        }
        
        # Mock GET Response (Content)
        mock_get_content = b"Line 1\nLine 2\nLine 3"
        
        # Configure Side Effects
        # Configure Side Effects
        def execute_side_effect(opcode, **kwargs):
            if opcode == OP_TASK_SEARCH_REPORT:
                return mock_task_res
            if opcode == OP_GET:
                # Return content in data
                return MagicMock(status=200, data=mock_get_content)
            return MagicMock(status=404)
            
        mock_client_instance.execute.side_effect = execute_side_effect
        # mock_client_instance.get_file.return_value = mock_get_content # REMOVED
        
        # Patch the instantiated client inside the CLI logic? 
        # The CLI instantiates `AgentClient(transport)`.
        # We need to mock `AgentClient` constructor or the class itself.
        
        with patch('client.cli.interactive_menu.AgentClient', return_value=mock_client_instance) as MockClientCls:
            # Inputs
            mock_input.side_effect = [
                "3", # Connect
                "127.0.0.1", # Manual IP (since not resolved)
                "TCP", # Mode
                "9", # Task Search
                "foo.txt", "pattern", # Args
                "0" # Exit
            ]
            
            cli = InteractiveCLI()
            # Preset server IP to skip DNS check prompt inside Connect if verified
            cli.state.server_ip = "127.0.0.1" 
             
            cli.start()
            
            output = mock_stdout.getvalue()
            
            # Verify Flow
            assert "Connected!" in output
            assert "Result too large. Artifact generated" in output
            assert "Auto-downloading..." in output
            assert "Downloaded Artifact" in output
            assert "Line 1" in output # Preview
            
            # Verify Calls
            # Verify Calls
            # Should have called execute(OP_TASK_SEARCH_REPORT, ...)
            # And execute(OP_GET, filename=...)
            
            # Check for GET call
            # We can't easily check 'assert_called_with' if multiple calls happened.
            # extracting calls:
            calls = mock_client_instance.execute.call_args_list
            
            # Simply check if OP_GET was called with correct filename
            found_get = False
            for call in calls:
                args, kwargs = call
                if args[0] == OP_GET and kwargs.get('filename') == "artifacts/test_result.txt":
                    found_get = True
                    break
            
            assert found_get, "execute(OP_GET, ...) not called for artifact"

if __name__ == '__main__':
    unittest.main()
