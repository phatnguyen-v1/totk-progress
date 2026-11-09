"""Local web app: TotK progress map from the save folder of TotK Recomp (or any progress.sav folder).

    python server.py [--save-dir DIR] [--port 8787] [--host 127.0.0.1] [--no-browser]

Without --save-dir it looks for profile\\save\\<user>\\ under %TOTK_DIR% or <drive>:\\Games\\TotK.
"""
import argparse
import json
import mimetypes
import os
import struct
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import savefile

HERE = Path(__file__).resolve().parent
WEB = HERE / 'web'
ASSETS = HERE / 'assets'
DEFAULT_INSTALLS = ([Path(os.environ['TOTK_DIR'])] if os.environ.get('TOTK_DIR') else []) + \
    [Path(f'{d}:/Games/TotK') for d in 'CDEFG'] + [Path.home() / 'Games' / 'TotK']


def find_save_dir(explicit):
    if explicit:
        p = Path(explicit)
        # Accept the install folder, profile\save, or the user folder itself
        for cand in (p, p / 'save', p / 'profile' / 'save'):
            users = [d for d in cand.glob('*') if d.is_dir() and any(d.glob('slot_0*/progress.sav'))]
            if any(cand.glob('slot_0*/progress.sav')):
                return cand
            if users:
                return max(users, key=lambda d: d.stat().st_mtime)
        sys.exit(f'No slot_0X/progress.sav found under {p}')
    for inst in DEFAULT_INSTALLS:
        users = [d for d in (inst / 'profile' / 'save').glob('*') if any(d.glob('slot_0*/progress.sav'))]
        if users:
            return max(users, key=lambda d: d.stat().st_mtime)
    sys.exit('Save folder not found. Pass --save-dir <TotK install folder or profile\\save>.')


class State:
    def __init__(self, save_dir):
        self.save_dir = save_dir
        self.map_data = json.loads((ASSETS / 'map_data.json').read_text(encoding='utf-8'))
        qfile = ASSETS / 'quests.json'
        qdata = json.loads(qfile.read_text(encoding='utf-8')) if qfile.exists() else {}
        self.quests = qdata.get('quests')
        self.logic = qdata.get('logic')
        self.cache = {}  # slot -> (mtime_ns, size, result)
        self.lock = threading.Lock()

    def slots(self):
        out = []
        for d in sorted(self.save_dir.glob('slot_0*')):
            f = d / 'progress.sav'
            if not f.is_file():
                continue
            st = f.stat()
            entry = {'slot': int(d.name[-1]), 'mtime': st.st_mtime}
            try:
                entry.update(savefile.save_info(f))
            except (savefile.SaveError, OSError) as e:
                entry['error'] = str(e)
            out.append(entry)
        return out

    def latest_slot(self):
        ok = [s for s in self.slots() if 'error' not in s]
        if not ok:
            return None
        return max(ok, key=lambda s: (s['mtime'], s['playtime']))['slot']

    def progress(self, slot):
        f = self.save_dir / f'slot_{slot:02d}' / 'progress.sav'
        st = f.stat()
        key = (st.st_mtime_ns, st.st_size)
        with self.lock:
            hit = self.cache.get(slot)
            if hit and hit[0] == key:
                return hit[1]
        # The game may be writing the file: retry a few times on a torn read
        last = None
        for _ in range(5):
            try:
                result = savefile.parse(f, self.map_data)
                if self.quests:
                    result['quests'] = savefile.parse_quests(f, self.quests, self.logic)
                break
            except (savefile.SaveError, struct.error, OSError) as e:
                last = e
                time.sleep(0.3)
        else:
            raise savefile.SaveError(f'could not read slot {slot}: {last}')
        result.update(slot=slot, mtime=st.st_mtime)
        with self.lock:
            self.cache[slot] = (key, result)
        return result


def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def send_json(self, obj, code=200):
            body = json.dumps(obj, separators=(',', ':')).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_file(self, path, cache=False):
            try:
                path = path.resolve()
                if not (path.is_relative_to(WEB) or path.is_relative_to(ASSETS)) or not path.is_file():
                    raise FileNotFoundError
            except (FileNotFoundError, OSError, ValueError):
                self.send_error(404)
                return
            data = path.read_bytes()
            ctype = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
            self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'max-age=86400' if cache else 'no-cache')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            p = url.path
            try:
                if p == '/api/slots':
                    self.send_json({'save_dir': str(state.save_dir), 'latest': state.latest_slot(),
                                    'slots': state.slots()})
                elif p == '/api/progress':
                    slot = q.get('slot', [''])[0]
                    slot = state.latest_slot() if slot in ('', 'latest') else int(slot)
                    if slot is None:
                        self.send_json({'error': 'no readable save'}, 404)
                    else:
                        self.send_json(state.progress(slot))
                elif p == '/data/map_data.json':
                    self.send_file(ASSETS / 'map_data.json', cache=True)
                elif p == '/data/quests.json':
                    if state.quests is None:
                        self.send_json({'error': 'quests.json missing: run python build_quests.py'}, 404)
                    else:
                        self.send_file(ASSETS / 'quests.json')
                elif p.startswith('/assets/'):
                    self.send_file(ASSETS / p[len('/assets/'):], cache=True)
                elif p in ('/', '/index.html'):
                    self.send_file(WEB / 'index.html')
                else:
                    self.send_file(WEB / p.lstrip('/'))
            except (ValueError, savefile.SaveError, OSError) as e:
                self.send_json({'error': str(e)}, 500)

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--save-dir')
    ap.add_argument('--port', type=int, default=int(os.environ.get('PORT', 8787)))
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--no-browser', action='store_true')
    args = ap.parse_args()

    if not (ASSETS / 'map_data.json').exists():
        sys.exit('Assets missing: run  python fetch_assets.py  first.')
    state = State(find_save_dir(args.save_dir))
    srv = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    url = f'http://{"localhost" if args.host in ("127.0.0.1", "0.0.0.0") else args.host}:{args.port}/'
    print(f'Save folder: {state.save_dir}')
    if state.quests is None:
        print('Quests: off (run  python build_quests.py  to enable)')
    else:
        print(f'Quests: {len(state.quests)}')
    print(f'Serving {url}  (Ctrl+C to stop)', flush=True)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
