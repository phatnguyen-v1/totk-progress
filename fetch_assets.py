"""Download the object data, icons and map images from lud99/totk-unexplored into assets/.

These come from the game's own files, so they are fetched to your machine, not shipped here.
Run once: python fetch_assets.py   (add --small for the 1500 px maps instead of 4500 px)
"""
import json
import sys
import urllib.request
from pathlib import Path

REPO = 'lud99/totk-unexplored'
REF = 'main'
RAW = f'https://raw.githubusercontent.com/{REPO}/{REF}/romfs/'
ROOT = Path(__file__).resolve().parent / 'assets'

ICONS = [
    'korok_hidden', 'korok_carry', 'shrine', 'lightroot', 'cave', 'bubbul', 'well', 'chasm',
    'location', 'hinox', 'talus', 'molduga', 'flux_construct', 'frox', 'gleeok', 'sages_will',
    'old_map', 'addison_sign', 'schema_stone', 'yiga_schematic', 'surface', 'sky', 'depths',
]


def fetch(rel, dest):
    if dest.exists() and dest.stat().st_size > 0:
        print('  have', rel)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    print('  get ', rel, end='', flush=True)
    req = urllib.request.Request(RAW + rel, headers={'User-Agent': 'totk-progress'})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    tmp = dest.with_suffix(dest.suffix + '.part')
    tmp.write_bytes(data)
    tmp.replace(dest)
    print(f' ({len(data) // 1024} KB)')


def main():
    size = 'small' if '--small' in sys.argv else 'medium'
    print('Data')
    fetch('map_data.json', ROOT / 'map_data.json')
    json.loads((ROOT / 'map_data.json').read_text(encoding='utf-8'))  # fail early if broken
    print('Icons')
    for name in ICONS:
        fetch(f'icons/{name}.png', ROOT / 'icons' / f'{name}.png')
    print(f'Maps ({size})')
    for layer in ('surface', 'sky', 'depths'):
        fetch(f'map/{layer}-{size}.png', ROOT / 'map' / f'{layer}.png')
    (ROOT / 'map' / 'size.txt').write_text(size)
    print('Done:', ROOT)


if __name__ == '__main__':
    main()
