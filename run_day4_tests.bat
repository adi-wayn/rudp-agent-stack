
@echo off
chcp 65001 > nul
set PYTHONPATH=.
echo Running Day 4 tests... > test_output_day4.txt
python -m unittest -v tests.integration.test_day4_client >> test_output_day4.txt 2>&1
if %ERRORLEVEL% NEQ 0 (
  echo FAILURE >> test_output_day4.txt
) else (
  echo SUCCESS >> test_output_day4.txt
)
echo Done. >> test_output_day4.txt
