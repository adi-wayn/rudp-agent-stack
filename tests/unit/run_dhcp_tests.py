import unittest
import sys

if __name__ == "__main__":
    from tests.unit.test_dhcp_client import TestDHCPClient
    with open('manual_test_results.log', 'w') as f:
        # Redirect stdout and stderr to the file
        sys.stdout = f
        sys.stderr = f
        
        suite = unittest.TestLoader().loadTestsFromTestCase(TestDHCPClient)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        print(f"\nTests run: {result.testsRun}")
        print(f"Errors: {len(result.errors)}")
        print(f"Failures: {len(result.failures)}")
