"""Download the object data, icons and map images from lud99/totk-unexplored into assets/.

These come from the game's own files, so they are fetched to your machine, not shipped here.
Run once: python fetch_assets.py   (add --small for the 1500 px maps instead of 4500 px)
"""
import json
import sys
import urllib.request

from paths import ASSETS

REPO = 'lud99/totk-unexplored'
REF = 'main'
RAW = f'https://raw.githubusercontent.com/{REPO}/{REF}/romfs/'

ICONS = [
    'korok_hidden', 'korok_carry', 'shrine', 'lightroot', 'cave', 'bubbul', 'well', 'chasm',
    'location', 'hinox', 'talus', 'molduga', 'flux_construct', 'frox', 'gleeok', 'sages_will',
    'old_map', 'addison_sign', 'schema_stone', 'yiga_schematic', 'surface', 'sky', 'depths',
]
# rough sizes in MB, only for the progress bar
MAP_MB = {'medium': 15.0, 'small': 2.0}


def have_assets(root=ASSETS):
    return (root / 'map_data.json').is_file() and all((root / 'map' / f'{l}.png').is_file()
                                                       for l in ('surface', 'sky', 'depths'))


def fetch_all(root=ASSETS, size='medium', progress=None):
    """Download everything missing. progress(fraction 0..1, message) is called as it goes."""
    files = [('map_data.json', root / 'map_data.json', 0.8, 'object data')]
    files += [(f'icons/{n}.png', root / 'icons' / f'{n}.png', 0.01, 'icons') for n in ICONS]
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
