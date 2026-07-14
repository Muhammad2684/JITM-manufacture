@echo off
REM JITM POS - Windows Build Script
REM Run this on Windows with Python and NSIS installed

echo === Installing dependencies ===
pip install pyinstaller openpyxl flask flask-login

echo === Building with PyInstaller ===
pyinstaller JITM.spec
if %errorlevel% neq 0 exit /b %errorlevel%

echo === Building NSIS installer ===
makensis installer.nsi
if %errorlevel% neq 0 (
    echo NSIS not found. Install NSIS from https://nsis.sourceforge.io/
    echo The PyInstaller build is ready at dist\JITM\
    pause
    exit /b 1
)

echo === Done ===
echo Installer: JITM POS Setup.exe
pause
