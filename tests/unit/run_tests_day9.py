import unittest
import sys
import os

# Ensure we can import from common
sys.path.append(os.getcwd())

from tests.unit.test_rudp_receiver_rwnd import TestRUDPReceiverRWND
from tests.unit.test_rudp_sender_rwnd import TestRUDPSenderRWND
from tests.unit.test_rudp_receiver import TestRUDPReceiver
from tests.unit.test_rudp_sender import TestRUDPSender

def run_tests():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestRUDPReceiverRWND))
    suite.addTest(unittest.makeSuite(TestRUDPSenderRWND))
    suite.addTest(unittest.makeSuite(TestRUDPReceiver))
    suite.addTest(unittest.makeSuite(TestRUDPSender))
    
    print("Starting Day 9 RUDP Flow Control Tests...")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print(f"\nResults: {result.wasSuccessful()}")
    print(f"Tests Run: {result.testsRun}")
    print(f"Errors: {len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    
    if not result.wasSuccessful():
        for failure in result.failures:
            print(f"FAILURE in {failure[0]}: {failure[1]}")
        for error in result.errors:
            print(f"ERROR in {error[0]}: {error[1]}")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
