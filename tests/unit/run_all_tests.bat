@echo off
echo Starting tests...
python -m unittest discover -v tests/unit > test_results.txt 2>&1
echo Done.
