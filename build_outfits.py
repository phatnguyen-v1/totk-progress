"""Build assets/outfits.json from your own Tears of the Kingdom game files (TotK Recomp's romfs folder).

    python build_outfits.py [--romfs <TotK Recomp folder>\\romfs] [--lang USen]

Every armor piece (RSDB/PouchActorInfo, PouchCategory Armor) with its upgrade levels (ArmorNextRankActor: each
Great Fairy upgrade is its own actor), the materials and rupees each upgrade takes (the actor pack's
EnhancementMaterial), its set (ArmorParam SeriesName) and effect, and where to get it, all from the game files:
  - shops: the ShopParam goods lists in the shopkeepers' and Bargainer statues' actor packs, placed where those
    actors stand on the map;
  - treasure chests with armor inside (the armor chests of map_data.json, which say what they hold).
The save has an IsGet.<actor> flag per piece and level, and the inventory (Pouch.Armor / Pouch.Material).
"""
import argparse
import io
import json
import re
import time
from pathlib import Path

import gamefiles
from build_mapdata import basename
from paths import ASSETS
from savefile import mmh3

OUT = ASSETS / 'outfits.json'
ICON_SIZE = 96   # px; shown at 44 css px in the list and 112 when open
SLOTS = {'Head': 'head', 'Upper': 'body', 'Lower': 'legs'}
TOWN_CATEGORIES = ('City', 'District', 'Stable')   # LocationArea kinds a shop is named after
# set names (the game has no text for them), by ArmorParam SeriesName
SETS = {
    'Hylia': 'Hylian set', 'HyliaArmor': "Soldier's set", 'Climb': 'Climbing set', 'Sheikah': 'Stealth set',
    'NightGlow': 'Radiant set', 'Gerudo': 'Desert Voe set', 'Goron': 'Flamebreaker set', 'Rito': 'Snowquill set',
    'Zora': 'Zora set', 'Rubber': 'Rubber set', 'Power': 'Barbarian set', 'Korok': 'Set of the Wild',
    'RoyalGuard': 'Royal Guard set', 'Ancient': 'Divine Helms', 'Dark': 'Dark set', 'Phantom': 'Phantom set',
    'PhantomGanon': 'Evil Spirit set', 'Tingle': "Tingle's set", 'Kishin': 'Fierce Deity set',
    'OcarinaOfTime': 'Set of Time', 'WindWaker': 'Set of the Wind', 'TwilightPrincess': 'Set of Twilight',
    'SkywardSword': 'Set of the Sky', 'Zelda1': 'Set of the Hero', 'Awakening': 'Set of Awakening',
    'ChemicalFire': 'Ember set', 'ChemicalIce': 'Frostbite set', 'ChemicalElectric': 'Charged set',
    'Diving': 'Glide set', 'LightEmission': "Miner's set", 'MagicArmor': 'Mystic set', 'NotSlippy': 'Froggy set',
    'UnderGround': 'Depths set', 'Yiga': 'Yiga set', 'Zonanium': 'Zonaite set', 'Archaic': 'Archaic set',
}
# pieces without a SeriesName that belong together: actor number -> set
GROUPS = {
    **{n: 'Gerudo jewelry' for n in ('024', '025', '026', '027', '028', '029')},
    **{n: 'Monster masks' for n in ('045', '055', '056', '1125', '022')},
    **{n: 'Archaic set' for n in ('1043', '1044')},
    **{n: 'Boots' for n in ('049', '141')},
}
EFFECTS = {
    'ResistCold': 'Cold resistance', 'ResistHot': 'Heat resistance', 'ResistElectric': 'Shock resistance',
    'ResistBurn': 'Flame guard', 'ResitLightning': 'Lightning proof', 'SwimSpeedUp': 'Swim speed up',
    'QuietnessUp': 'Stealth up', 'ClimbSpeedUp': 'Climb speed up', 'AttackUp': 'Attack up',
    'AttackUpCold': 'Attack up (cold)', 'AttackUpHot': 'Attack up (heat)', 'AttackUpThunderstorm': 'Attack up (storms)',
    'SandMoveUp': 'Sand speed up', 'SnowMoveUp': 'Snow speed up', 'MiasmaGuard': 'Gloom resistance',
    'NightGlow': 'Glows at night', 'LightEmission': 'Glow', 'DivingMobilityUp': 'Skydive mobility up',
    'NotSlippy': 'Slip resistance', 'RupeeGuard': 'Rupee padding', 'DecreaseZonauEnergy': 'Zonaite charge up',
    'EnableUseSwordBeam': 'Master Sword beam up', 'MaskMoriblin': 'Disguise (Moblins)',
    'MaskLizalfos': 'Disguise (Lizalfos)', 'MaskLynel': 'Disguise (Lynels)', 'MaskAll': 'Disguise (monsters)',
    'MaskBokoblin': 'Disguise (Bokoblins)', 'MaskHorablin': 'Disguise (Horriblins)', 'Disguise': 'Disguise',
}


def p3(t):
    t = t if isinstance(t, (list, tuple)) else [t['x'], t['y'], t['z']]
    return [round(t[0], 1), round(t[1], 1), round(t[2], 1)]


def effect_label(kind):
    return EFFECTS.get(kind, re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', kind)) if kind and kind != 'None' else ''


def pack_params(rf, actor):
    """(ArmorParam, EnhancementMaterial) of an actor pack; either may be {}."""
    path = f'Pack/Actor/{actor}.pack.zs'
    if path not in rf.files:
        return {}, {}
    files = gamefiles.sarc(rf.read(path))
    armor = next((gamefiles.byml(d) for n, d in files.items() if n.startswith('Component/ArmorParam/')), {})
    table = next((gamefiles.byml(d) for n, d in files.items() if n.startswith('GameParameter/GameParameterTable/')), {})
    ref = ((table or {}).get('Components') or {}).get('EnhancementMaterial', '').lstrip('?')
    enh = gamefiles.byml(files[ref]) if ref in files else {}
    return armor or {}, enh or {}


def shop_lists(rf, log):
    """{shop actor: [(armor actor, only_if_found, later, price offset, currency)]} from every ShopParam selling armor.

    ReleaseRequirements: IsCheckGetFlag alone = on sale once you've found the piece yourself (the Hateno fashion
    shop's second list, most Bargainer statue goods); a ReleaseGameData flag = added to the stock later."""
    out = {}
    for path in rf.find('Pack/Actor/', '.pack.zs'):
        actor = basename(path)
        if not actor.startswith(('Npc_', 'TwnObj_DemonStatue', 'FldObj_AmosStatue')):
            continue
        try:
            files = gamefiles.sarc(rf.read(path))
        except Exception:
            continue
        param = next((d for n, d in files.items() if n.startswith('Component/ShopParam/')), None)
        if param is None:
            continue
        items = []
        for g in gamefiles.byml(param).get('GoodsList') or []:
            item = basename(g.get('Actor', ''))
            if item.startswith('Armor_'):
                req = g.get('ReleaseRequirements') or {}
                later = bool(req.get('IsCheckReleaseGameData') and req.get('ReleaseGameData'))
                items.append((item, bool(req.get('IsCheckGetFlag')) and not later, later,
                              g.get('PriceOffset') or 0, g.get('Currency') or 'Rupee'))
        if items:
            out[actor] = items
    log(f'outfits: {len(out)} shops sell armor')
    return out


def write_icons(rf, pieces, out_dir, log):
    """The inventory picture of each piece (UI/Tex/Icon/<actor>.bntx.zs) as <piece id>.webp. Sets piece['icon']."""
    from PIL import Image
    import maptiles
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in pieces:
        rel = f"UI/Tex/Icon/{p['id']}.bntx.zs"
        if rel not in rf.files:
            continue
        try:
            data = rf.read(rel)
            w, h, bgra, _ = maptiles.decode_texture(data, data.find(b'BRTI'))
            img = Image.frombytes('RGBA', (w, h), bgra, 'raw', 'BGRA')
            img.thumbnail((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, 'WEBP', quality=88, method=6)
            (out_dir / f"{p['id']}.webp").write_bytes(buf.getvalue())
            p['icon'] = True
            n += 1
        except Exception as e:   # the list still works without the picture
            log(f"outfits: no icon for {p['id']}: {type(e).__name__}: {e}")
    log(f'outfits: {n} icons -> {out_dir}')


def build(romfs, out=OUT, lang='USen', log=print, placed=None, map_data=None):
    """`placed` ({actor: [positions]}) and `map_data` come from build_mapdata.build; without them the map data is
    built here first (the placement data is only read there)."""
    rf = romfs if isinstance(romfs, gamefiles.Romfs) else gamefiles.Romfs(romfs)
    if placed is None or map_data is None:
        import build_mapdata
        placed = {}
        build_mapdata.build(rf.folder, ASSETS / 'map_data.json', lang=lang, log=log, placed=placed)
        map_data = json.loads((ASSETS / 'map_data.json').read_text(encoding='utf-8'))
    mals = gamefiles.sarc(rf.read(rf.find(f'Mals/{lang}.Product.', '.sarc.zs')[-1]))

    def msgs(name):
        f = f'{name}.msbt'
        return gamefiles.msbt(mals[f]) if f in mals else {}

    items, npcs = msgs('ActorMsg/PouchContent'), msgs('ActorMsg/Npc')
    pouch = {r['__RowId']: r for r in gamefiles.byml(rf.read(rf.find('RSDB/PouchActorInfo.', '.byml.zs')[-1]))}
    armor = {a: r for a, r in pouch.items() if r.get('PouchCategory') == 'Armor'}

    def name(actor):
        return (items.get(f'{actor}_Name') or '').strip()

    def item_id(actor):
        """Some materials are named, and kept in the inventory, as the picked-up actor (Item_Plant_O ->
        Item_PlantGet_O, Animal_Fish_M -> Item_FishGet_M)."""
        alt = re.sub(r'^(?:Item|Animal)_([A-Za-z]+)_', r'Item_\1Get_', actor)
        return alt if not name(actor) and name(alt) else actor

    # ---- places, to say where a shop or chest is: the nearest town or stable for a shop, else the nearest place
    loc_names = {**msgs('LocationMsg/Location'), **msgs('LocationMsg/Dungeon')}
    towns = []
    for field in ('MainField', 'MinusField'):
        la = gamefiles.byml(rf.read(f'Banc/{field}/LocationArea/{field}.locationarea.byml.zs')) or {}
        for cat in TOWN_CATEGORIES:
            for e in la.get(cat) or []:
                loc = basename(e['LocationName'])
                if e.get('Trans') and loc_names.get(loc):
                    towns.append((loc_names[loc], p3(e['Trans'][0])))
    markers = [(o['display_name'], p3(o['position'])) for k in ('locations', 'caves', 'wells', 'chasms', 'shrines')
               for o in map_data.get(k, []) if o.get('display_name')]

    def place(pt, shop=False):
        d2 = lambda m: (m[1][0] - pt[0]) ** 2 + (m[1][2] - pt[2]) ** 2 + (m[1][1] - pt[1]) ** 2
        near = [m for m in towns if d2(m) < 300 ** 2] if shop else []
        best = min(near or markers, key=d2, default=None)
        return best[0] if best else ''

    # ---- pieces and their upgrade chains
    nxt = {a: basename(r.get('ArmorNextRankActor', '')) for a, r in armor.items()}
    upgraded = set(filter(None, nxt.values()))
    pieces, by_actor, seen_names = [], {}, set()
    for base in sorted(armor, key=lambda a: (int(re.match(r'Armor_(\d+)', a).group(1)) if re.match(r'Armor_\d+', a) else 1e9, a)):
        nm = name(base)
        slot = SLOTS.get(base.rsplit('_', 1)[-1])
        if base in upgraded or not nm or not slot or nm in seen_names:
            continue   # an upgrade, a hood-down variant (_B), an unused piece, or a second copy of a name
        seen_names.add(nm)
        chain = [base]
        while nxt.get(chain[-1]) in armor and len(chain) < 6:
            chain.append(nxt[chain[-1]])
        params = [pack_params(rf, a) for a in chain]
        levels = []
        for i, act in enumerate(chain):
            mats, rupees = [], None
            if i:   # what it takes to go from the level below to this one
                enh = params[i - 1][1]
                for m in enh.get('Items') or []:
                    item = item_id(basename(m.get('Actor', '')))
                    mats.append([item, name(item) or item, m.get('Number', 1)])
                rupees = enh.get('Price') or None
            levels.append({'actor': act, 'flag': mmh3(f'IsGet.{act}'), 'mats': mats, 'rupees': rupees})
        series = params[0][0].get('SeriesName') or ''
        num = re.match(r'Armor_(\d+)', base).group(1)
        set_name = SETS.get(series) or GROUPS.get(num) or nm
        piece = {
            'id': base, 'name': nm, 'slot': slot, 'set': set_name, 'series': series, 'sort': len(pieces),
            'effect': effect_label(armor[base].get('ArmorEffectType')),
            'price': armor[base].get('BuyingPrice') if (armor[base].get('BuyingPrice') or 0) > 0 else None,
            'levels': levels, 'sources': [],
        }
        pieces.append(piece)
        for act in chain:
            by_actor[act] = piece

    def add(actor, src):
        p = by_actor.get(actor)
        if p is None:
            return
        key = (src['type'], src.get('who'), src.get('place'), tuple(src.get('points', [[]])[0]))
        if all((s['type'], s.get('who'), s.get('place'), tuple(s.get('points', [[]])[0])) != key for s in p['sources']):
            p['sources'].append(src)

    # ---- shops: shopkeepers and Bargainer statues, where they stand
    # The Bargainer statues sell (nearly) the same goods: one source per piece, with every statue on the map.
    shops, statue_goods, statue_pts = shop_lists(rf, log), {}, []
    for actor in [a for a in shops if not a.startswith('Npc_')]:
        for g in shops.pop(actor):
            statue_goods.setdefault(g[0], g)
        statue_pts += [p3(t) for t in placed.get(actor, [])[:1]]
    entries = [(name(a) or npcs.get(f'{a}_Name') or npcs.get(re.sub(r'_[A-Za-z]+\d*$', '', a) + '_Name') or '', None,
                [p3(t) for t in placed.get(a, [])[:4]], goods) for a, goods in shops.items()]
    entries.append(('Bargainer Statue', '', statue_pts, list(statue_goods.values())))
    for who, where, pts, goods in entries:
        if not who:
            continue
        if where is None:
            where = ' · '.join(dict.fromkeys(w for w in (place(p, shop=True) for p in pts) if w))
        for item, only_found, later, offset, currency in goods:
            price = (armor.get(item, {}).get('BuyingPrice') or 0) + offset
            add(item, {'type': 'shop', 'who': who, 'place': where, 'points': pts, 'price': price if price > 0 else None,
                       'currency': 'poe' if currency == 'MinusRupee' else 'rupee', 'rebuy': only_found, 'later': later})

    # ---- treasure chests with armor inside (sky, surface, caves and the Depths)
    for o in map_data.get('armor_chests', []):
        if o.get('drop'):
            pt = p3(o['position'])
            add(o['drop'], {'type': 'chest', 'place': place(pt), 'points': [pt]})

    for p in pieces:   # first-time sources first; shops that only sell again what you've found go last
        p['sources'].sort(key=lambda s: {'chest': 0, 'shop': 1}[s['type']] + (2 if s.get('rebuy') else 0))

    write_icons(rf, pieces, Path(out).parent / 'outfiticons', log)
    sets = {}
    for p in pieces:
        sets.setdefault(p['set'], []).append(p)
    data = {'lang': lang, 'built': int(time.time()),
            'sets': [{'name': k, 'pieces': v} for k, v in sorted(sets.items(), key=lambda kv: kv[1][0]['sort'])]}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.part')
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(out)
    nosrc = [p['name'] for p in pieces if not p['sources']]
    log(f'outfits: {len(pieces)} pieces in {len(sets)} sets; no source for {len(nosrc)}: {", ".join(nosrc)}')
    return data


def main():
    from build_quests import DEFAULT_ROMFS
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--romfs', help='TotK Recomp romfs folder (default: TOTK_DIR or <drive>:\\Games\\TotK\\romfs)')
    ap.add_argument('--out', default=str(OUT))
    ap.add_argument('--lang', default='USen')
    a = ap.parse_args()
    romfs = Path(a.romfs) if a.romfs else next((p for p in DEFAULT_ROMFS if (p / 'index.json').exists()), None)
    if not romfs or not (romfs / 'index.json').exists():
        ap.error('romfs folder not found; pass --romfs')
    build(romfs, a.out, a.lang)


if __name__ == '__main__':
    main()
