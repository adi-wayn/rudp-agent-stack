import unittest
import sys
import os

# Ensure root is in path
sys.path.append(os.getcwd())

def run_all_tests():
    print("=== STARTING FULL TEST SUITE ===")
    loader = unittest.TestLoader()
    suite = loader.discover('tests/unit')
    
    # We use a stream that we can also read from if needed, 
    # but for now TextTestRunner to stdout is what we want.
    with open("test_results.txt", "w") as f:
        # Redirect stdout/stderr to the file for the duration of the test run
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        sys.stdout = f
        sys.stderr = f
        
        try:
            runner = unittest.TextTestRunner(verbosity=2, stream=f)
            result = runner.run(suite)
            
            f.write("\n=== TEST SUMMARY ===\n")
            f.write(f"Tests Run: {result.testsRun}\n")
            f.write(f"Errors: {len(result.errors)}\n")
            f.write(f"Failures: {len(result.failures)}\n")
            f.write(f"Overall Success: {result.wasSuccessful()}\n")
            
            if not result.wasSuccessful():
                f.write("\n--- FAILURES ---\n")
                for f_item in result.failures: # Renamed f to f_item to avoid conflict with file handle f
                    f.write(str(f_item[0]) + "\n")
                    f.write(str(f_item[1]) + "\n")
                f.write("\n--- ERRORS ---\n")
                for e_item in result.errors: # Renamed e to e_item to avoid conflict with file handle f
                    f.write(str(e_item[0]) + "\n")
                    f.write(str(e_item[1]) + "\n")
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
    
    print("Tests completed. Results written to test_results.txt")
    # Exit with 0 so the command tool doesn't think it failed if we just want to see output
    sys.exit(0)

if __name__ == "__main__":
    run_all_tests()
