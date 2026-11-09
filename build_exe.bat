@echo off
rem Builds dist\TotKProgressMap.exe (one file, no console window). Needs Python 3.10+.
cd /d "%~dp0"
python -m pip install --upgrade -r requirements.txt pyinstaller || goto :fail
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name TotKProgressMap ^
  --add-data "web;web" ^
  --hidden-import zstandard ^
  server.py || goto :fail
echo.
echo Built: %~dp0dist\TotKProgressMap.exe
goto :eof
:fail
echo Build failed.
exit /b 1
