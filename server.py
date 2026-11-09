"""TotK Progress Map: a local web app showing your Tears of the Kingdom progress from your saves.

    TotKProgressMap.exe            (or: python server.py [--save-dir DIR] [--port 8787] [--no-browser])

On first start the page shows a setup screen: pick the TotK Recomp install folder (found automatically
when possible), then it downloads the map data and builds the quest list from your game files.
"""
import argparse
import json
import mimetypes
import os
import string
import struct
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import savefile
from paths import APP_NAME, ASSETS, CONFIG, DATA, FROZEN, LOG, VERSION, WEB

APP_ID = 'totk-progress-map'
CSRF_HEADER = 'X-TotK-Progress'   # POSTs must carry it, so other websites can't drive this local app


# ---------------------------------------------------------------- install folders

def _saves_under(folder):
    """The most recently used <user> folder with slot_0X/progress.sav under `folder` (or folder itself)."""
    folder = Path(folder)
    try:
        if any(folder.glob('slot_0*/progress.sav')):
            return folder
        users = [d for d in folder.glob('*') if d.is_dir() and any(d.glob('slot_0*/progress.sav'))]
    except OSError:
        return None
    return max(users, key=lambda d: d.stat().st_mtime) if users else None


def inspect(path):
    """Check a folder the user picked. Accepts the install folder or anything inside it (romfs, profile, save)."""
    p = Path(path).expanduser()
    info = {'input': str(p), 'path': str(p), 'game': False, 'save_dir': None, 'slots': 0, 'ok': False, 'notes': []}
    if not p.is_dir():
        info['notes'].append('This folder does not exist.')
        return info
    root = None
    for cand in [p, *list(p.parents)[:4]]:
        if (cand / 'romfs' / 'index.json').is_file() or (cand / 'profile' / 'save').is_dir() or (cand / 'totk.exe').is_file():
            root = cand
            break
    if root:
        info['path'] = str(root)
        info['game'] = (root / 'romfs' / 'index.json').is_file()
        save_dir = _saves_under(root / 'profile' / 'save')
    else:
        save_dir = _saves_under(p) or _saves_under(p / 'save')   # a plain save folder (e.g. from an emulator)
    if save_dir:
        info['save_dir'] = str(save_dir)
        info['slots'] = sum(1 for _ in save_dir.glob('slot_0*/progress.sav'))
    if root and not info['game']:
        info['notes'].append('Game files (romfs) not found here, so the Quests tab will be off.')
    if not root and not save_dir:
        info['notes'].append("This doesn't look like a TotK Recomp folder: no totk.exe, romfs or profile\\save inside.")
    elif not save_dir:
        info['notes'].append("No saves yet. Play until the game saves once, and the map will pick it up.")
    info['ok'] = bool(root or save_dir)
    info['exe'] = bool(root and (root / 'totk.exe').is_file())
    return info


def detect_installs():
    """Look for TotK Recomp installs in the usual places. Fast: only a couple of folder levels per drive."""
    roots = []
    if os.environ.get('TOTK_DIR'):
        roots.append(Path(os.environ['TOTK_DIR']))
    drives = [Path(f'{d}:/') for d in string.ascii_uppercase if os.path.exists(f'{d}:/')] if os.name == 'nt' else [Path('/')]
    home = Path.home()
    bases = [*drives, *[d / 'Games' for d in drives], home, home / 'Games', home / 'Desktop', home / 'Downloads']
    for base in bases:
        try:
            for d in base.iterdir():
                if d.is_dir() and ((d / 'totk.exe').is_file() or (d / 'romfs' / 'index.json').is_file()):
                    roots.append(d)
        except OSError:
            continue
    seen, out = set(), []
    for r in roots:
        key = str(r.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        info = inspect(r)
        if info['ok']:
            out.append(info)
    out.sort(key=lambda i: (not i['save_dir'], not i['game']))
    return out


def load_config():
    try:
        return json.loads(CONFIG.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding='utf-8')


# ---------------------------------------------------------------- state

class State:
    def __init__(self, save_override=None):
        self.lock = threading.Lock()
        self.cfg = load_config()
        self.save_override = save_override
        self.install = None
        self.save_dir = None
        self.map_data = self.quests = self.logic = None
        self.cache = {}
        self.job = {'running': False, 'progress': 0.0, 'message': '', 'error': None, 'done': False}
        self.reload()

    def reload(self):
        """Re-read config, install folder and assets."""
        self.install = inspect(self.cfg['install_dir']) if self.cfg.get('install_dir') else None
        sd = self.save_override or (self.install or {}).get('save_dir')
        self.save_dir = Path(sd) if sd else None
        mp = ASSETS / 'map_data.json'
        self.map_data = json.loads(mp.read_text(encoding='utf-8')) if mp.is_file() else None
        qfile = ASSETS / 'quests.json'
        qdata = json.loads(qfile.read_text(encoding='utf-8')) if qfile.is_file() else {}
        self.quests, self.logic = qdata.get('quests'), qdata.get('logic')
        with self.lock:
            self.cache.clear()

    def ready(self):
        import fetch_assets
        return bool(self.save_dir) and self.map_data is not None and fetch_assets.have_assets()

    def setup_status(self, with_candidates=False):
        import fetch_assets
        st = {
            'version': VERSION, 'ready': self.ready(), 'install': self.install,
            'save_override': self.save_override, 'data_dir': str(DATA),
            'assets': {'map': fetch_assets.have_assets(), 'quests': self.quests is not None},
            'job': dict(self.job),
        }
        if with_candidates:
            st['candidates'] = detect_installs()
        return st

    def start_setup(self, folder):
        info = inspect(folder)
        if not info['ok']:
            raise ValueError(' '.join(info['notes']) or 'Not a TotK folder.')
        if self.job['running']:
            raise ValueError('Setup is already running.')
        self.cfg['install_dir'] = info['path']
        save_config(self.cfg)
        self.job = {'running': True, 'progress': 0.0, 'message': 'Starting…', 'error': None, 'done': False}
        threading.Thread(target=self._setup_job, args=(info,), daemon=True).start()
        return info

    def needs_game_build(self):
        """True when game files are available but the map wasn't built from them yet (e.g. after an update)."""
        import fetch_assets
        return bool(self.install and self.install.get('game')) and not (
            fetch_assets.have_game_tiles() and (ASSETS / 'source.json').is_file())

    def start_upgrade(self):
        if self.install and not self.job['running']:
            self.job = {'running': True, 'progress': 0.0, 'message': 'Updating the map from your game files…',
                        'error': None, 'done': False, 'upgrade': True}
            threading.Thread(target=self._setup_job, args=(self.install,), daemon=True).start()

    def _setup_job(self, info):
        import fetch_assets
        job = self.job

        def stage(lo, hi):
            def prog(frac, msg):
                job['progress'] = round(lo + (hi - lo) * frac, 3)
                job['message'] = msg
            return prog

        try:
            if info.get('game'):
                romfs = Path(info['path']) / 'romfs'
                import gamefiles
                import maptiles
                import build_mapdata
                rf = gamefiles.Romfs(romfs)
                stage(0, 0.6)(0, 'Drawing the map from your game files…')
                maptiles.build_tiles(rf, ASSETS / 'tiles', progress=stage(0, 0.6))
                stage(0.6, 0.75)(0, 'Finding shrines, Koroks and everything else in your game files…')
                build_mapdata.build(romfs, ASSETS / 'map_data.json', log=lambda m: stage(0.6, 0.75)(0.5, m[:80]))
                stage(0.75, 0.8)(0, 'Adding Korok puzzle details…')
                ref = fetch_assets.fetch_reference()
                if ref:
                    data = json.loads((ASSETS / 'map_data.json').read_text(encoding='utf-8'))
                    build_mapdata.merge_reference(data, ref)
                    build_mapdata.write(data, ASSETS / 'map_data.json')
                else:
                    job['warning'] = 'Korok puzzle details were skipped (no internet). Everything else is ready.'
                (ASSETS / 'source.json').write_text(json.dumps({'map': 'game', 'korok_details': bool(ref),
                                                                'built': time.time()}))
                import shutil
                for old in ('map', 'icons'):  # downloaded map images and icons from older versions
                    shutil.rmtree(ASSETS / old, ignore_errors=True)
                stage(0.8, 1)(0, 'Reading the quest list from your game files…')
                try:
                    import build_quests
                    build_quests.build(romfs, ASSETS / 'quests.json', log=lambda m: None)
                except Exception as e:  # the map still works without quests
                    traceback.print_exc()
                    job['warning'] = f'Quest list not built: {e}'
            elif not fetch_assets.have_assets():
                try:
                    fetch_assets.fetch_all(ASSETS, 'medium', stage(0, 1))
                except OSError as e:
                    raise RuntimeError(f"Couldn't download the map data ({e}). Check your internet connection and try again.")
            job['progress'], job['message'] = 1.0, 'Done'
            self.reload()
            job['done'] = True
        except Exception as e:
            traceback.print_exc()
            job['error'] = f'{type(e).__name__}: {e}'
        finally:
            job['running'] = False

    # ---- saves
    def slots(self):
        out = []
        if not self.save_dir:
            return out
        for d in sorted(self.save_dir.glob('slot_0*')):
            f = d / 'progress.sav'
            if not f.is_file():
                continue
            st = f.stat()
            entry = {'slot': int(d.name[-1]), 'mtime': st.st_mtime}
            try:
                entry.update(savefile.save_info(f))
            except (savefile.SaveError, OSError, struct.error) as e:
                entry['error'] = str(e)
            out.append(entry)
        return out

    def latest_slot(self):
        ok = [s for s in self.slots() if 'error' not in s]
        return max(ok, key=lambda s: (s['mtime'], s['playtime']))['slot'] if ok else None

    def progress(self, slot):
        f = self.save_dir / f'slot_{slot:02d}' / 'progress.sav'
        st = f.stat()
        key = (st.st_mtime_ns, st.st_size)
        with self.lock:
            hit = self.cache.get(slot)
            if hit and hit[0] == key:
                return hit[1]
        last = None
        for _ in range(5):  # the game may be writing the file: retry on a torn read
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


# ---------------------------------------------------------------- folder picker

_dialog_lock = threading.Lock()


def pick_folder(initial=None):
    """Open the normal Windows folder picker on top of everything. Returns a path or None."""
    with _dialog_lock:
        import tkinter
        from tkinter import filedialog
        root = tkinter.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        try:
            chosen = filedialog.askdirectory(parent=root, mustexist=True, initialdir=initial or str(Path.home()),
                                             title='Select your TotK Recomp folder (the one with totk.exe)')
        finally:
            root.destroy()
        return chosen or None


# ---------------------------------------------------------------- HTTP

def make_handler(state, server_ref):
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
                if not (path.is_relative_to(WEB.resolve()) or path.is_relative_to(ASSETS.resolve())) or not path.is_file():
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
                if p == '/api/ping':
                    self.send_json({'app': APP_ID, 'version': VERSION})
                elif p == '/api/setup':
                    self.send_json(state.setup_status(with_candidates=q.get('scan', ['0'])[0] == '1'))
                elif p in ('/api/slots', '/api/progress') and not state.ready():
                    self.send_json({'error': 'setup required', 'setup': True}, 409)
                elif p == '/api/slots':
                    self.send_json({'save_dir': str(state.save_dir), 'latest': state.latest_slot(), 'slots': state.slots(),
                                    'job': state.job})
                elif p == '/api/progress':
                    slot = q.get('slot', [''])[0]
                    slot = state.latest_slot() if slot in ('', 'latest') else int(slot)
                    if slot is None:
                        self.send_json({'error': 'no readable save yet'}, 404)
                    else:
                        self.send_json(state.progress(slot))
                elif p == '/data/map_data.json':
                    self.send_file(ASSETS / 'map_data.json', cache=True)
                elif p == '/data/quests.json':
                    if state.quests is None:
                        self.send_json({'error': 'quest list not built'}, 404)
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

        def do_POST(self):
            if self.headers.get(CSRF_HEADER) != '1':
                self.send_json({'error': 'forbidden'}, 403)
                return
            try:
                length = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(length) or b'{}') if length else {}
            except ValueError:
                self.send_json({'error': 'bad request'}, 400)
                return
            p = urlparse(self.path).path
            try:
                if p == '/api/setup/browse':
                    start = body.get('initial') or (state.install or {}).get('path')
                    chosen = pick_folder(start)
                    self.send_json({'path': chosen, 'info': inspect(chosen) if chosen else None})
                elif p == '/api/setup/check':
                    self.send_json(inspect(body.get('path', '')))
                elif p == '/api/setup/apply':
                    info = state.start_setup(body.get('path', ''))
                    self.send_json({'ok': True, 'info': info})
                elif p == '/api/quit':
                    self.send_json({'ok': True})
                    threading.Thread(target=lambda: (time.sleep(0.3), server_ref[0].shutdown()), daemon=True).start()
                else:
                    self.send_json({'error': 'not found'}, 404)
            except ValueError as e:
                self.send_json({'error': str(e)}, 400)

    return Handler


class Server(ThreadingHTTPServer):
    allow_reuse_address = False   # on Windows SO_REUSEADDR would let a second copy share the port
    daemon_threads = True


def already_running(host, port):
    try:
        with urllib.request.urlopen(f'http://{host}:{port}/api/ping', timeout=1.5) as r:
            return json.loads(r.read()).get('app') == APP_ID
    except (OSError, ValueError):
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--save-dir', help='read saves from this folder instead of the configured install')
    ap.add_argument('--port', type=int, default=int(os.environ.get('PORT', 8787)))
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--no-browser', action='store_true')
    args = ap.parse_args()

    if FROZEN:  # no console window: keep a log next to the data
        DATA.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(LOG, 'a', encoding='utf-8', buffering=1)
    print(f'--- {APP_NAME} {VERSION} starting {time.ctime()}')

    browse_host = 'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host
    srv = None
    for port in range(args.port, args.port + 10):
        if already_running('127.0.0.1', port):   # second launch: just show the page again
            print(f'Already running on {port}')
            if not args.no_browser:
                webbrowser.open(f'http://{browse_host}:{port}/')
            return
        try:
            server_ref = [None]
            state = State(args.save_dir)
            srv = Server((args.host, port), make_handler(state, server_ref))
            server_ref[0] = srv
            break
        except OSError:
            continue
    if srv is None:
        print('No free port found.')
        return
    url = f'http://{browse_host}:{port}/'
    print(f'Data folder: {DATA}')
    print(f'Install: {(state.install or {}).get("path")}  ready={state.ready()}')
    if state.ready() and state.needs_game_build():
        print('Map not built from the game files yet: updating in the background')
        state.start_upgrade()
    print(f'Serving {url}', flush=True)
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    print('Stopped.')


if __name__ == '__main__':
    main()
