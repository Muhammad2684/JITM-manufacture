@echo off
cd /d "%~dp0"
echo Installing JITM POS...
echo.

:: Create desktop shortcut
set "SHORTCUT=%USERPROFILE%\Desktop\JITM POS.lnk"
set "TARGET=%~dp0JITM.exe"
set "ICON=%~dp0JITM.exe"

powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%SHORTCUT%');$s.TargetPath='%TARGET%';$s.WorkingDirectory='%~dp0';$s.IconLocation='%ICON%,0';$s.Description='JITM POS System';$s.Save()"

if exist "%SHORTCUT%" (
    echo Desktop shortcut created successfully.
    echo.
    echo Double-click "JITM POS" on your desktop to start.
    echo The app will open in your browser automatically.
) else (
    echo Failed to create shortcut. Try running as Administrator.
)
echo.
pause
