"""Decode the in-game map tiles (UI/Map/MainField/*.bntx.zs) from your own TotK files into PNG tiles.

Layers: G = surface, S = sky, U = depths. Each layer is a 12 x 10 grid of tiles of 1000 x 1000 world
units (x -6000..6000, z -5000..5000), in five detail levels: 00 = 3000 px, 01 = 840 px, 02 = 300 px,
03 = 135 px, 04 = 27 px. Tiles are ASTC compressed (sRGB) in the Switch's block-linear layout.
"""
import struct

import texture2ddecoder

ASTC_BLOCKS = {0x2D: (4, 4), 0x2E: (5, 4), 0x2F: (5, 5), 0x30: (6, 5), 0x31: (6, 6), 0x32: (8, 5),
               0x33: (8, 6), 0x34: (8, 8), 0x35: (10, 5), 0x36: (10, 6), 0x37: (10, 8), 0x38: (10, 10),
               0x39: (12, 10), 0x3A: (12, 12)}


def _div_up(a, b):
    return (a + b - 1) // b


def deswizzle(data, width_blocks, height_blocks, bpp, block_height_log2):
    """Tegra X1 block-linear -> linear, in units of compressed blocks of `bpp` bytes."""
    block_height = 1 << block_height_log2
    gobs_wide = _div_up(width_blocks * bpp, 64)
    row_bytes = width_blocks * bpp
    out = bytearray(row_bytes * height_blocks)
    mv = memoryview(data)
    for y in range(height_blocks):
        y_base = (y // (8 * block_height)) * 512 * block_height * gobs_wide + (y % (8 * block_height) // 8) * 512 \
            + ((y % 8) // 2) * 64 + (y % 2) * 16
        o = y * row_bytes
        for x in range(width_blocks):
            xb = x * bpp
            addr = y_base + (xb // 64) * 512 * block_height + ((xb % 64) // 32) * 256 + ((xb % 32) // 16) * 32 + (xb % 16)
            out[o:o + bpp] = mv[addr:addr + bpp]
            o += bpp
    return bytes(out)


# Block-compressed formats besides ASTC: kind -> (bytes per 4x4 block, decoder)
BC_FORMATS = {0x1A: (8, 'decode_bc1'), 0x1C: (16, 'decode_bc3'), 0x1D: (8, 'decode_bc4'),
              0x1E: (16, 'decode_bc5'), 0x20: (16, 'decode_bc7')}


def textures(data):
    """Every texture in a BNTX file: [(name, BRTI offset)]."""
    out, i = [], data.find(b'BRTI')
    while i >= 0:
        name_at = struct.unpack_from('<Q', data, i + 0x60)[0]
        n = struct.unpack_from('<H', data, name_at)[0]
        out.append((data[name_at + 2:name_at + 2 + n].decode('utf-8', 'replace'), i))
        i = data.find(b'BRTI', i + 4)
    return out


def decode_texture(data, i):
    """Decode the BRTI texture at offset i (first mip level) -> (width, height, BGRA bytes, kind)."""
    fmt = struct.unpack_from('<I', data, i + 0x1C)[0]
    width, height = struct.unpack_from('<II', data, i + 0x24)
    layout = struct.unpack_from('<I', data, i + 0x34)[0]
    image_size = struct.unpack_from('<I', data, i + 0x50)[0]
    ptrs = struct.unpack_from('<Q', data, i + 0x70)[0]
    mip0 = struct.unpack_from('<Q', data, ptrs)[0]
    kind = fmt >> 8
    if kind in ASTC_BLOCKS:
        bw, bh = ASTC_BLOCKS[kind]
        bpp, decode = 16, lambda raw: texture2ddecoder.decode_astc(raw, width, height, bw, bh)
    elif kind in BC_FORMATS:
        bw = bh = 4
        bpp, fn = BC_FORMATS[kind]
        decode = lambda raw: getattr(texture2ddecoder, fn)(raw, width, height)
    else:
        raise ValueError(f'unsupported texture format 0x{fmt:04x}')
    raw = deswizzle(data[mip0:mip0 + image_size], _div_up(width, bw), _div_up(height, bh), bpp, layout & 7)
    return width, height, decode(raw), kind


def decode_bntx(data):
    """First texture of a BNTX file -> (width, height, RGBA bytes)."""
    i = data.find(b'BRTI')
    if i < 0:
        raise ValueError('no BRTI texture')
    width, height, bgra, _ = decode_texture(data, i)
    rgba = bytearray(bgra)
    rgba[0::4], rgba[2::4] = bgra[2::4], bgra[0::4]
    return width, height, bytes(rgba)


LAYERS = {'surface': 'G', 'sky': 'S', 'depths': 'U'}
# Bump when the tile choice or drawing changes: installs then redraw their tiles. 2: complete sky tiles
# instead of transparent overlays (two sky tiles were brown squares).
TILES_VERSION = 2


def pick_variants(romfs, prefix):
    """{(layer, lod, col, row): romfs path} choosing the fully revealed, complete variant of each tile.

    Names are <L>_<CC>-<RR>_<LOD> plus suffix parts: region letters (T revealed / F not) and A/B world-state
    letters, e.g. _TT, _T_A, _T_A_A. A tile with fewer parts than its siblings is a transparent overlay
    (just islands, nothing behind them), so the most parts wins first, then the most T, then A over B.
    """
    import re
    rx = re.compile(r'([GSU])_(\d\d)-(\d\d)_(\d\d)((?:_[TFAB]+)*)\.bntx\.zs$')
    best = {}
    for path in romfs.find(prefix):
        m = rx.search(path)
        if not m:
            continue
        layer, col, row, lod, suffix = m.groups()
        parts = [x for x in suffix.split('_') if x]
        letters = ''.join(parts)
        score = (len(parts), letters.count('T') - letters.count('F'), letters.count('A') - letters.count('B'))
        key = (layer, lod, int(col), int(row))
        if key not in best or score > best[key][0]:
            best[key] = (score, path)
    return {k: v[1] for k, v in best.items()}


# The detail levels the map uses, coarse to fine. 00 (3000 px a tile) is for zooming in as far as the game's own map;
# each of its tiles is cut into SPLIT x SPLIT pieces so the page loads only the 750 px pieces on screen.
LODS = ('02', '01', '00')
SPLIT = {'00': 4}


def build_tiles(romfs, out_dir, lods=LODS, progress=None):
    """Decode the chosen map tiles to out_dir/<layer>/<lod>/<col>-<row>.webp (a split level: <col>-<row>-<sx>-<sy>.webp,
    sx/sy the piece's column and row inside the tile). Tiles already there are kept, so adding a level later only
    draws that level. Returns the number of tiles."""
    import json
    from pathlib import Path
    out_dir = Path(out_dir)
    report = progress or (lambda f, m: None)
    # Existing tiles are kept so an interrupted setup resumes, but not tiles drawn by older tile code.
    try:
        old = json.loads((out_dir / 'meta.json').read_text(encoding='utf-8')).get('version')
    except (OSError, ValueError):
        old = TILES_VERSION
    if old != TILES_VERSION:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)
    chosen = pick_variants(romfs, 'UI/Map/MainField/')
    todo = [(name, lod, col, row, path) for (code, lod, col, row), path in sorted(chosen.items())
            for name, c in LAYERS.items() if c == code and lod in lods]
    from PIL import Image
    for i, (name, lod, col, row, path) in enumerate(todo):
        n = SPLIT.get(lod, 1)
        pieces = [(out_dir / name / lod / (f'{col}-{row}.webp' if n == 1 else f'{col}-{row}-{sx}-{sy}.webp'), sx, sy)
                  for sy in range(n) for sx in range(n)]
        if not all(dest.is_file() for dest, _, _ in pieces):
            pieces[0][0].parent.mkdir(parents=True, exist_ok=True)
            w, h, px = decode_bntx(romfs.read(path))
            img = Image.frombytes('RGBA', (w, h), px).convert('RGB')
            pw, ph = w // n, h // n
            for dest, sx, sy in pieces:
                tmp = dest.with_suffix('.part')
                part = img if n == 1 else img.crop((sx * pw, sy * ph, (sx + 1) * pw, (sy + 1) * ph))
                part.save(tmp, 'WEBP', quality=80, method=4)
                tmp.replace(dest)
        report((i + 1) / len(todo), f'Drawing the {name} map… {i + 1}/{len(todo)}')
    (out_dir / 'meta.json').write_text(json.dumps({
        'version': TILES_VERSION, 'built': int(__import__('time').time()), 'source': 'game', 'format': 'webp', 'lods': list(lods),
        'split': {k: v for k, v in SPLIT.items() if k in lods}, 'cols': 12, 'rows': 10, 'tile_world': 1000,
        'origin': [-6000, -5000], 'layers': list(LAYERS)}))
    return len(todo)
