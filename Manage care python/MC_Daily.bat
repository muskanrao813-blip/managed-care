@echo off
REM ============================================================
REM MANAGED CARE 3.0 - DAILY AUTOMATION WITH PROGRESS
REM FIXED VERSION - Accurate logic for copying from /data
REM ============================================================

setlocal enabledelayedexpansion

cd /d "C:\Users\muskan.rao\Documents\managed-care-platform\Manage care python"

echo.
echo ========== MANAGED CARE DAILY AUTOMATION ==========
echo.
echo Starting at %date% %time%
echo Running 16 scripts (takes 1-2 hours)...
echo.

REM Run PowerShell script and show output in real-time
powershell.exe -ExecutionPolicy Bypass -NoProfile -File ".\DAILY_AUTOMATION_COMPLETE.ps1"

set ExitCode=!ERRORLEVEL!

echo.
echo ========== RESULT ==========
echo.
if %ExitCode% equ 0 (
    echo SUCCESS - All scripts completed
    echo.
    echo Dashboard updating to Render (2-3 min)...
    echo URL: https://managed-care-dashboard.onrender.com/
) else (
    echo FAILED - Exit code: %ExitCode%
    echo Check log: logs\daily_*.log
)

echo.
echo Press any key to close...
pause

exit /b %ExitCode%
