@echo off
cd /d "%~dp0"
echo Starting JITM POS...
echo If the app crashes, check error.log for details.
echo.
JITM.exe
echo.
echo The app has exited. Press any key to close.
pause >nul
