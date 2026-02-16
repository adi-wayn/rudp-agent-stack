@echo off
chcp 65001
set PYTHONPATH=%CD%
python -m tests.integration.test_day3_upload
if %ERRORLEVEL% NEQ 0 (
    echo Test Failed with ErrorLevel %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)
echo Test Completed Successfully
