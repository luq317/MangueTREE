@echo off
REM Build MangueTREE for Windows. Requires Python 3.11+.
REM Double-click this file OR run it from a Command Prompt inside this folder.
echo === MangueTREE - Windows build ===
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller
pip install --no-deps .
pyinstaller --noconfirm MangueTREE.spec
echo.
echo Done! The application is at: dist\MangueTREE\MangueTREE.exe
echo Compress the dist\MangueTREE folder to distribute it.
pause
