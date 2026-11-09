"""Map icons taken from your own TotK files: the game's map UI icons, item icons and Hyrule Compendium
pictures, written as PNGs to assets/gameicons/ (plus meta.json listing them). Icons the game has no
picture for keep this project's own SVG (web/icons/).

Sources:
- UI/LayoutArchive/Common.*.blarc.zs -> timg/__Combined.bntx: map UI icons. `^w` textures are white
  glyphs with alpha; `^s` ones are one-channel masks (BC4) that the game colours in its layouts, so they
  are coloured here.
- UI/Tex/Icon/<actor>.bntx.zs: item icons (256 px, with alpha).
- UI/Tex/PictureBook/<actor>_Icon.bntx.zs: compendium pictures (168 px photos).
"""
import json
import time
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import gamefiles
import maptiles
from paths import ASSETS

VERSION = 2  # bump when the icon set or its drawing changes: the app then rebuilds it
SIZE = 96  # output px; markers are drawn at 20-24 css px, so this stays sharp on high-dpi screens

# name: (kind, source, colour)
#   ui    - white glyph from the combined UI textures
#   mask  - one-channel mask from the combined UI textures, filled with colour
#   item  - UI/Tex/Icon/<source>
#   photo - UI/Tex/PictureBook/<source>_Icon, cut to a circle
RECIPES = {
    'korok_hidden': ('ui', 'MapIconKorok^w', None),
    'korok_carry': ('ui', 'MapIconKorok_x2^w', None),
    'shrine': ('mask', 'MapIconDungeon_L_FrameIcon^s', (245, 170, 60)),
    'lightroot': ('mask', 'MapIconArrivalPoint_L_FrameIcon^s', (205, 235, 105)),
    'cave': ('ui', 'MapIconCaveM_72x72^w', None),
    'well': ('ui', 'MapIconCaveS_72x72^w', None),
    'chasm': ('ui', 'MapIconCaveL_72x72^w', None),
    'location': ('ui', 'MapIconBuildingVillage_58x58^w', None),
    'bubbul': ('item', 'CaveMasterMedal', None),
    'hinox': ('photo', 'Enemy_Giant_Middle', None),
    'talus': ('photo', 'Enemy_Golem_Middle', None),
    'molduga': ('photo', 'Enemy_Sandworm', None),
    'flux_construct': ('photo', 'Enemy_Zonau_BlockMaster_Middle', None),
    'frox': ('photo', 'Enemy_Mogurudo_Middle', None),
    'gleeok': ('photo', 'Enemy_Drake_Fire', None),
    'sages_will': ('item', 'Obj_SageWill', None),
    'old_map': ('item', 'Obj_TreasureMap_00', None),
    'schema_stone': ('item', 'Obj_AutoBuilderDraft_00', None),
    'yiga_schematic': ('item', 'Obj_AutoBuilderDraftAssassin_00', None),
    'player': ('mask', 'Nt_MapPlayerIconNew_00^s', (255, 214, 64)),
    'sky': ('mask', 'MapTabIcon_Sky^s', (255, 255, 255)),
    'surface': ('mask', 'MapTabIcon_Ground^s', (255, 255, 255)),
    'depths': ('mask', 'MapTabIcon_Cave^s', (255, 255, 255)),
}


def _image(data, offset):
    w, h, bgra, kind = maptiles.decode_texture(data, offset)
    img = Image.frombytes('RGBA', (w, h), bgra, 'raw', 'BGRA')
    if kind == 0x1D:  # BC4: one channel (red) = coverage
        img = Image.merge('RGBA', (*[Image.new('L', img.size, 255)] * 3, img.getchannel('R')))
    return img


def _fit(img, box):
    # crop to what's visible; masks have faint noise around the glyph, so ignore near-transparent pixels
    visible = img.getchannel('A').point(lambda v: 255 if v > 100 else 0).getbbox()
    if visible:  # keep a little of the soft edge
        l, t, r, b = visible
        visible = (max(l - 2, 0), max(t - 2, 0), min(r + 2, img.width), min(b + 2, img.height))
    img = img.crop(visible or (0, 0, *img.size))
    scale = box / max(img.size)   # up or down: some glyphs are only ~25 px in their texture
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    out = Image.new('RGBA', (SIZE, SIZE))
    out.alpha_composite(img, ((SIZE - img.width) // 2, (SIZE - img.height) // 2))
    return out


def _with_outline(img, width=5, opacity=0.85):
    """Dark outline + soft shadow so light icons stay readable on the bright map."""
    alpha = img.getchannel('A')
    edge = alpha.filter(ImageFilter.MaxFilter(width)).filter(ImageFilter.GaussianBlur(1.5))
    edge = edge.point(lambda v: int(v * opacity))
    out = Image.new('RGBA', img.size, (20, 16, 10, 0))
    out.putalpha(edge)
    out.alpha_composite(img)
    return out


def _tint(mask, colour):
    out = Image.new('RGBA', mask.size, (*colour, 0))
    out.putalpha(mask.getchannel('A'))
    return out


def _photo(img):
    side = min(img.size)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((SIZE - 8, SIZE - 8), Image.LANCZOS)
    mask = Image.new('L', img.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, img.width - 1, img.height - 1), fill=255)
    out = Image.new('RGBA', (SIZE, SIZE))
    ImageDraw.Draw(out).ellipse((0, 0, SIZE - 1, SIZE - 1), fill=(20, 16, 10, 255))
    ImageDraw.Draw(out).ellipse((2, 2, SIZE - 3, SIZE - 3), fill=(232, 214, 160, 255))
    img.putalpha(ImageChops.multiply(img.getchannel('A'), mask))
    out.alpha_composite(img, (4, 4))
    return out


def build(romfs, out=ASSETS / 'gameicons', log=print):
    """Write <name>.png for every icon found; returns the list of names written."""
    rf = romfs if isinstance(romfs, gamefiles.Romfs) else gamefiles.Romfs(romfs)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ui = None
    written = []
    for name, (kind, src, colour) in RECIPES.items():
        try:
            if kind in ('ui', 'mask'):
                if ui is None:
                    path = rf.find('UI/LayoutArchive/Common.', '.blarc.zs')[0]
                    ui = gamefiles.sarc(rf.read(path))['timg/__Combined.bntx']
                    ui_index = dict(maptiles.textures(ui))
                img = _image(ui, ui_index[src])
                if kind == 'mask':
                    img = _tint(img, colour)
                img = _with_outline(_fit(img, SIZE - 12))
            elif kind == 'item':
                data = rf.read(f'UI/Tex/Icon/{src}.bntx.zs')
                img = _with_outline(_fit(_image(data, data.find(b'BRTI')), SIZE - 8), width=3, opacity=0.6)
            else:
                data = rf.read(f'UI/Tex/PictureBook/{src}_Icon.bntx.zs')
                img = _photo(_image(data, data.find(b'BRTI')))
        except Exception as e:  # keep the app's own icon for this one
            log(f'icon {name}: {type(e).__name__}: {e}')
            continue
        img.save(out / f'{name}.png', optimize=True)
        written.append(name)
    (out / 'meta.json').write_text(json.dumps({'version': VERSION, 'icons': written, 'built': int(time.time())}), encoding='utf-8')
    log(f'{len(written)} game icons -> {out}')
    return written


if __name__ == '__main__':
    import argparse
    from build_quests import DEFAULT_ROMFS
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--romfs', help='TotK Recomp romfs folder (default: TOTK_DIR or <drive>:\\Games\\TotK\\romfs)')
    ap.add_argument('--out', default=str(ASSETS / 'gameicons'))
    a = ap.parse_args()
    romfs = a.romfs or next((p for p in DEFAULT_ROMFS if (p / 'index.json').exists()), None)
    if not romfs:
        ap.error('romfs folder not found; pass --romfs')
    build(romfs, a.out)
