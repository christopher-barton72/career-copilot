@echo off
setlocal
cd /d "%~dp0"
set "CAREER_PYTHON=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"

if not exist "%CAREER_PYTHON%" (
  echo Python was not found at:
  echo %CAREER_PYTHON%
  echo.
  echo Edit start-career-copilot.cmd if Python is installed elsewhere.
  pause
  exit /b 1
)

echo Starting Career Copilot at http://127.0.0.1:8765
echo Keep this window open. Press Ctrl+C to stop.
"%CAREER_PYTHON%" -m career_copilot

if errorlevel 1 pause
endlocal
