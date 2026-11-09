@echo off
rem Run TotK Progress Map from source. The page walks you through setup on first start.
cd /d "%~dp0"
python -c "import zstandard" 2>nul || python -m pip install --user -r requirements.txt
python server.py %*
