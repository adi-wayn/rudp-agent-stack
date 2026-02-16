@echo off
chcp 65001 > nul
set PYTHONPATH=.
echo Running tests... > test_output.txt
python -m tests.integration.test_day3_upload >> test_output.txt 2>&1
echo Done. >> test_output.txt
