"""Where things live. Running from source: next to the code. As the packaged exe: web files inside the
bundle, data (assets, config, log) in %LOCALAPPDATA%\\TotKProgressMap."""
import os
import sys
from pathlib import Path

APP_NAME = 'TotKProgressMap'
VERSION = '1.4.0'
FROZEN = getattr(sys, 'frozen', False)
HERE = Path(__file__).resolve().parent
BUNDLE = Path(getattr(sys, '_MEIPASS', HERE))
WEB = BUNDLE / 'web'

if FROZEN:
    DATA = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / APP_NAME
else:
    DATA = HERE
ASSETS = DATA / 'assets'
CONFIG = DATA / 'config.json'
LOG = DATA / 'app.log'
