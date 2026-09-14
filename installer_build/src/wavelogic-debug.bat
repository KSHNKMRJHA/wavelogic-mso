@echo off
rem ============================================================
rem  WaveLogic MSO - DEBUG launcher
rem  Runs the bundled Python/Streamlit directly in THIS console
rem  window so you can watch the server's live output.
rem  The browser opens automatically (server.headless=false).
rem ============================================================
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONDONTWRITEBYTECODE=1
echo Starting WaveLogic MSO in debug mode...
echo Server URL: http://127.0.0.1:8501
echo.
"%~dp0python\python.exe" -m streamlit run app.py ^
    --server.address=127.0.0.1 ^
    --server.headless=false ^
    --server.showEmailPrompt=false ^
    --browser.gatherUsageStats=false ^
    --global.developmentMode=false
echo.
echo The server stopped (exit code %ERRORLEVEL%).
pause