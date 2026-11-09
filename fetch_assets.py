"""Fallback map assets from lud99/totk-unexplored, for setups without TotK Recomp game files
(e.g. emulator saves). With game files, build_mapdata.py and maptiles.py make everything locally and
only lud99's map_data.json is used, to add Korok puzzle details (see fetch_reference).

Run: python fetch_assets.py   (add --small for 1500 px maps instead of 4500 px)
"""
import json
import sys
import urllib.request

from paths import ASSETS

REPO = 'lud99/totk-unexplored'
REF = 'main'
RAW = f'https://raw.githubusercontent.com/{REPO}/{REF}/romfs/'

# rough sizes in MB, only for the progress bar
MAP_MB = {'medium': 15.0, 'small': 2.0}


def have_game_tiles(root=ASSETS):
    return (root / 'tiles' / 'meta.json').is_file()


def have_assets(root=ASSETS):
    """Map data plus a base map: tiles drawn from the game, or the downloaded map images."""
    maps = have_game_tiles(root) or all((root / 'map' / f'{l}.png').is_file() for l in ('surface', 'sky', 'depths'))
    return (root / 'map_data.json').is_file() and maps


def fetch_reference(timeout=30):
    """lud99's map_data.json as a dict, or None when offline. Small (~0.8 MB), not stored."""
    try:
        req = urllib.request.Request(RAW + 'map_data.json', headers={'User-Agent': 'totk-progress-map'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except (OSError, ValueError):
        return None


def fetch_all(root=ASSETS, size='medium', progress=None):
    """Download everything missing. progress(fraction 0..1, message) is called as it goes."""
    files = [('map_data.json', root / 'map_data.json', 0.8, 'object data')]
    files += [(f'map/{l}-{size}.png', root / 'map' / f'{l}.png', MAP_MB[size], f'{l} map') for l in ('surface', 'sky', 'depths')]
    total = sum(w for *_, w, _ in files)
    done = 0.0
    report = progress or (lambda f, m: None)
    for rel, dest, weight, label in files:
        if dest.is_file() and dest.stat().st_size > 0:
            done += weight
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(RAW + rel, headers={'User-Agent': 'totk-progress-map'})
        tmp = dest.with_suffix(dest.suffix + '.part')
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'wb') as out:
            length = int(r.headers.get('Content-Length') or 0)
            got = 0
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                part = min(got / length, 1.0) if length else 0.5
                report((done + weight * part) / total, f'Downloading {label}… {got / 1e6:.1f} MB')
        tmp.replace(dest)
        done += weight
        report(done / total, f'Downloaded {label}')
    json.loads((root / 'map_data.json').read_text(encoding='utf-8'))  # fail early if broken
    (root / 'map' / 'size.txt').write_text(size)
    report(1.0, 'Map data ready')


def main():
    size = 'small' if '--small' in sys.argv else 'medium'
    last = [-1]

    def show(frac, msg):
        pct = int(frac * 100)
        if pct != last[0]:
            last[0] = pct
            print(f'\r{pct:3d}%  {msg:<50}', end='', flush=True)

    fetch_all(ASSETS, size, show)
    print('\nDone:', ASSETS)


if __name__ == '__main__':
    main()
