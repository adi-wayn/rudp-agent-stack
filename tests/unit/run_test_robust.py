
import unittest
import sys
import os
import traceback

if __name__ == '__main__':
    try:
        print("Starting robust test runner...")
        
        # Add project root to path
        sys.path.append(os.getcwd())
        
        from tests.integration.test_day4_client import TestDay4Client

        with open("test_results_day4.txt", "w") as f:
            runner = unittest.TextTestRunner(stream=f, verbosity=2)
            suite = unittest.TestLoader().loadTestsFromTestCase(TestDay4Client)
            result = runner.run(suite)
            
        print("Test run complete. Results written to test_results_day4.txt")
        if result.wasSuccessful():
            print("SUCCESS")
            # Optionally write success marker
            with open("test_success.marker", "w") as m:
                m.write("PASSED")
            sys.exit(0)
        else:
            print("FAILURE")
            sys.exit(1)
            
    except Exception as e:
        with open("error.log", "w") as f:
            f.write(f"Fatal Error: {e}\n")
            f.write(traceback.format_exc())
        sys.exit(1)
