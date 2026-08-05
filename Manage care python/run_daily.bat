@echo off
REM Batch wrapper for Task Scheduler
REM Runs PowerShell script for daily managed care pipeline

powershell.exe -ExecutionPolicy Bypass -File "C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python\run_all_scripts.ps1"

exit /b %errorlevel%
