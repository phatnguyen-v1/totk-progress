@echo off
rem TotK Progress Map: downloads the map assets on first run, builds the quest list, then serves http://localhost:8787/
cd /d "%~dp0"
if not exist "assets\map_data.json" (
  echo First run: downloading map data, icons and maps ^(about 45 MB^)...
  python fetch_assets.py || goto :fail
)
if not exist "assets\quests.json" (
  python -c "import zstandard" 2>nul || (
    echo Installing the zstandard package for reading the game's quest files...
    python -m pip install --user zstandard
  )
  echo Building the quest list from your TotK Recomp game files...
  python build_quests.py || echo Quest list not built: the map still works. See README.md.
)
python server.py %*
goto :eof
:fail
echo.
echo Asset download failed. Check your internet connection and run start.bat again.
pause
