@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || exit /b 1
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "RE6-ARC-Studio" --icon icon.ico ^
  --add-data "ui;ui" ^
  --collect-all webview --collect-all texture2ddecoder ^
  app.py || exit /b 1
echo.
echo Built: dist\RE6-ARC-Studio.exe
