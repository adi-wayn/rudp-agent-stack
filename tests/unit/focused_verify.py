import unittest
import sys
import os

# Ensure root is in path
sys.path.append(os.getcwd())

from tests.unit.test_rudp_receiver_rwnd import TestRUDPReceiverRWND
from tests.unit.test_rudp_sender_rwnd import TestRUDPSenderRWND

def run_focused_tests():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestRUDPReceiverRWND))
    suite.addTest(unittest.makeSuite(TestRUDPSenderRWND))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    with open("common/verification.txt", "w") as f:
        f.write("DAY 9 RUDP FLOW CONTROL VERIFICATION\n")
        f.write("====================================\n")
        f.write(f"Tests Run: {result.testsRun}\n")
        f.write(f"Success: {result.wasSuccessful()}\n")
        if not result.wasSuccessful():
            f.write("\nFAILURES/ERRORS:\n")
            for item in result.failures + result.errors:
                f.write(f"--- {item[0]} ---\n")
                f.write(f"{item[1]}\n")
    
    sys.exit(0)

if __name__ == "__main__":
    run_focused_tests()
