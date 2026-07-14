@echo off
REM JITM POS - Onefile Windows Build Script
REM Run this on Windows with Python installed

echo === Installing dependencies ===
pip install pyinstaller openpyxl flask flask-login pystray pillow

echo === Cleaning old builds ===
if exist "dist\JITM.exe" del "dist\JITM.exe"
if exist "dist\JITM\" rmdir /s /q "dist\JITM\"
if exist "build\" rmdir /s /q "build\"

echo === Building single executable ===
pyinstaller --onefile --noconsole ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --hidden-import "routes.auth" ^
    --hidden-import "routes.products" ^
    --hidden-import "routes.pos" ^
    --hidden-import "routes.customers" ^
    --hidden-import "routes.dashboard" ^
    --hidden-import "routes.suppliers" ^
    --hidden-import "routes.settings" ^
    --hidden-import "routes.summary" ^
    --hidden-import "routes.categories" ^
    --hidden-import "routes.sizes" ^
    --hidden-import "routes.purchase_invoices" ^
    --hidden-import "routes.purchase_returns" ^
    --hidden-import "routes.accounts" ^
    --hidden-import "routes.transactions" ^
    --hidden-import "routes.ledger" ^
    --hidden-import "routes.payroll" ^
    --hidden-import "routes.reports" ^
    --hidden-import "routes.data_management" ^
    --hidden-import "database" ^
    --name "JITM" ^
    --icon "static\icon.ico" ^
    app.py

if %errorlevel% neq 0 (
    echo PyInstaller build failed!
    pause
    exit /b %errorlevel%
)

echo === Build complete ===
echo Executable: dist\JITM.exe
echo.
echo To create an installer, run: makensis installer.nsi
pause
