
import unittest
import sys
import os
import traceback

if __name__ == '__main__':
    try:
        print("Starting RUDP Receiver verification...")
        
        # Add project root to path
        sys.path.append(os.getcwd())
        
        from tests.unit.test_rudp_receiver import TestRUDPReceiver

        with open("rudp_test_results.txt", "w", encoding='utf-8') as f:
            runner = unittest.TextTestRunner(stream=f, verbosity=2)
            suite = unittest.TestLoader().loadTestsFromTestCase(TestRUDPReceiver)
            result = runner.run(suite)
            
        print("Test run complete. Results written to rudp_test_results.txt")
        if result.wasSuccessful():
            print("SUCCESS")
            # Write success marker
            with open("rudp_test_success.marker", "w") as m:
                m.write("PASSED")
            sys.exit(0)
        else:
            print("FAILURE")
            sys.exit(1)
            
    except Exception as e:
        with open("rudp_test_error.log", "w", encoding='utf-8') as f:
            f.write(f"Fatal Error: {e}\n")
            f.write(traceback.format_exc())
        print(f"Fatal Error: {e}")
        sys.exit(1)
