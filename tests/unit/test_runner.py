import unittest
import sys
import os

# Ensure the root directory is in the path
sys.path.append(os.getcwd())

from tests.unit.test_rudp_receiver import TestRUDPReceiver

def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestRUDPReceiver)
    runner = unittest.TextTestRunner(verbosity=2)
    with open('test_results.txt', 'w', encoding='utf-8') as f:
        # Redirect stdout and stderr to the file
        sys.stdout = f
        sys.stderr = f
        result = runner.run(suite)
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        
    print(f"Tests finished. Success: {result.wasSuccessful()}")
    sys.exit(0 if result.wasSuccessful() else 1)

if __name__ == '__main__':
    run_tests()
