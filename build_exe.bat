@echo off
rem Builds dist\TotKProgressMap.exe (one file, no console window). Needs Python 3.10+.
cd /d "%~dp0"
python -m pip install --upgrade -r requirements.txt pyinstaller || goto :fail
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name TotKProgressMap --icon app.ico ^
  --add-data "web;web" ^
  --hidden-import zstandard --hidden-import texture2ddecoder --hidden-import PIL.WebPImagePlugin --hidden-import PIL.PngImagePlugin ^
  --hidden-import webview --collect-all webview --hidden-import segno ^
  server.py || goto :fail
echo.
echo Built: %~dp0dist\TotKProgressMap.exe
goto :eof
:fail
echo Build failed.
exit /b 1
