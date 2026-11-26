@echo off
cd /d "%~dp0"
echo.
echo   File Organizer
echo   Open http://127.0.0.1:8767/ in your browser
echo   Press Ctrl+C here to stop the server
echo.
python -m uvicorn app:app --host 127.0.0.1 --port 8767
pause
