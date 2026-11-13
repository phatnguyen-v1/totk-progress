"""Where things live. Running from source: next to the code. As the packaged app: web files inside the
bundle, data (assets, config, log) in %LOCALAPPDATA%\\TotKProgressMap on Windows and in
$XDG_DATA_HOME/TotKProgressMap (~/.local/share/TotKProgressMap) on Linux."""
import os
import sys
from pathlib import Path

APP_NAME = 'TotKProgressMap'
VERSION = '1.8.0'
FROZEN = getattr(sys, 'frozen', False)
HERE = Path(__file__).resolve().parent
BUNDLE = Path(getattr(sys, '_MEIPASS', HERE))
WEB = BUNDLE / 'web'

WINDOWS = os.name == 'nt'
GAME_EXE = 'totk.exe' if WINDOWS else 'totk'   # TotK Recomp's game binary in the install folder

if FROZEN and WINDOWS:
    DATA = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / APP_NAME
elif FROZEN:
    DATA = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share') / APP_NAME
else:
    DATA = HERE
ASSETS = DATA / 'assets'
CONFIG = DATA / 'config.json'
LOG = DATA / 'app.log'
