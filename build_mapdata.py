"""Build assets/map_data.json (collectibles, places, bosses) from your own TotK Recomp game files.

    python build_mapdata.py [--romfs <TotK Recomp install>\\romfs] [--lang USen]

Everything comes from the game's own indexes and placement data:
- Banc/<Field>/LocationArea: shrines, lightroots, caves (+ Bubbul frogs), wells, chasms, named places
- Banc/MainField/HiddenKorok: Korok seeds and Korok friends (by instance ID)
- Banc/<Field>/<section>_Static|Dynamic, Sky, Cave, DeepHole: bosses, chests with Sage's Wills,
  old maps and Yiga schematics, Addison's signboards
- RSDB/PouchActorInfo: which armor an old map leads to; Banc/MinusField/TreasureMap
- Mals/<lang>: names
Save flags are murmur3 hashes of '<Prefix>.<instance ID or name>' (see docs/PROGRESS.md).
"""
import argparse
import json
import re
import sys
from pathlib import Path

import gamefiles
from paths import ASSETS
from savefile import mmh3

OUT = ASSETS / 'map_data.json'

# The 12 schema stones are handed out by event scripts, not stored in an index: which place gives which.
SCHEMA_SITES = {
    'Obj_AutoBuilderDraft_00': 'SmeltShopGolem_10', 'Obj_AutoBuilderDraft_01': 'MinusField_Rito',
    'Obj_AutoBuilderDraft_02': 'SmeltShopGolem_01', 'Obj_AutoBuilderDraft_03': 'SmeltShopGolem_03',
    'Obj_AutoBuilderDraft_04': 'MinusField_Hateno', 'Obj_AutoBuilderDraft_05': 'SmeltShopGolem_09',
    'Obj_AutoBuilderDraft_06': 'SmeltShopGolem_06', 'Obj_AutoBuilderDraft_07': 'SmeltShopGolem_02',
    'Obj_AutoBuilderDraft_08': 'SmeltShopGolem_07', 'Obj_AutoBuilderDraft_09': 'MinusField_Goron',
    'Obj_AutoBuilderDraft_10': 'MinusField_StartPoint', 'Obj_AutoBuilderDraft_11': 'MinusField_StartPoint',
}
BOSSES = {'Giant': 'hinoxes', 'Golem': 'taluses', 'Sandworm': 'moldugas', 'Zonau': 'flux_constructs',
          'Mogurudo': 'froxes', 'Drake': 'gleeoks'}
KOROK_TYPES = {'Npc_HiddenKorokFly': 'Flying Korok', 'Npc_HiddenKorokGround': 'Hidden Korok'}
# LocationArea categories shown as named places (the ones discovered by visiting); shops, districts,
# small spots and towers are left out.
PLACE_CATEGORIES = re.compile(r'^(City|DragonTears|Dungeon|SkyArchipelago|Stable|SpotBig.*|SpotMiddle\w+)$')


def basename(path):
    return path.rsplit('/', 1)[-1].split('.', 1)[0] if path else ''


def pos(t):
    return {'x': round(t[0], 2), 'y': round(t[1], 2), 'z': round(t[2], 2)}


def build(romfs, out=OUT, lang='USen', log=print):
    rf = gamefiles.Romfs(romfs)
    mals = gamefiles.sarc(rf.read(rf.find(f'Mals/{lang}.Product.', '.sarc.zs')[-1]))

    def msgs(name):
        f = f'{name}.msbt'
        return gamefiles.msbt(mals[f]) if f in mals else {}

    names = {**msgs('LocationMsg/Location'), **msgs('LocationMsg/Dungeon')}
    drafts = msgs('ActorMsg/AutoBuilderDraft')
    data = {k: [] for k in ['shrines', 'lightroots', 'hidden_koroks', 'carry_koroks', 'bubbuls', 'locations', 'caves',
                            'wells', 'chasms', 'hinoxes', 'taluses', 'moldugas', 'flux_constructs', 'froxes', 'gleeoks',
                            'old_maps', 'sages_wills', 'addison_signposts', 'schema_stones', 'yiga_schematics']}

    # ---- places, from the game's location index
    log('Reading the location index…')
    places = {}
    for field in ('MainField', 'MinusField'):
        la = gamefiles.byml(rf.read(f'Banc/{field}/LocationArea/{field}.locationarea.byml.zs')) or {}
        for cat, entries in la.items():
            for e in entries or []:
                name = basename(e['LocationName'])
                trans = e.get('Trans') or []
                if not trans:
                    continue
                places[name] = trans[0]
                display = names.get(name, name)
                if cat == 'Shrine':
                    data['shrines'].append({'internal_name': name, 'display_name': display,
                                            'completion_hash': mmh3(f'DungeonState.{name}'), 'position': pos(trans[0])})
                elif cat == 'CheckPoint':
                    data['lightroots'].append({'internal_name': name, 'display_name': display,
                                               'completion_hash': mmh3(f'ArrivalPointState.{name}'), 'position': pos(trans[0])})
                elif cat in ('CaveEntranceNormal', 'CaveEntranceSpecial', 'CaveEntranceWell'):
                    key = {'CaveEntranceNormal': 'caves', 'CaveEntranceSpecial': 'chasms', 'CaveEntranceWell': 'wells'}[cat]
                    if key == 'caves' and name.startswith('DeepHole'):
                        key = 'chasms'
                    for t in trans:  # one marker per entrance
                        data[key].append({'internal_name': name, 'display_name': display,
                                          'completion_hash': mmh3(f'IsVisitLocation.{name}'), 'position': pos(t)})
                    markers = e.get('CaveMarkerInfo') or []
                    if markers and not any(b['internal_name'] == name for b in data['bubbuls']):
                        data['bubbuls'].append({'internal_name': name, 'display_name': display,
                                                'completion_hash': mmh3(f'IsGetCaveMasterMedal.{name}'),
                                                'position': pos(markers[0]['Trans'])})
                elif PLACE_CATEGORIES.match(cat):
                    data['locations'].append({'display_name': display, 'completion_hash': mmh3(f'IsVisitLocation.{name}'),
                                              'position': pos(trans[0])})
        # device dispensers count as places on the map too
        rb = gamefiles.byml(rf.read(f'Banc/{field}/RecycleBox/{field}.recyclebox.byml.zs')) or {}
        for iid, e in rb.items():
            data['locations'].append({'display_name': 'Device Dispenser', 'completion_hash': mmh3(f'RecycleBoxData.{iid}.IsVisit'),
                                      'position': pos(e['Trans'])})

    # ---- Korok seeds and Korok friends
    log('Reading Koroks…')
    hk = gamefiles.byml(rf.read('Banc/MainField/HiddenKorok/MainField.hiddenkorok.byml.zs'))

    # ---- all placed actors (bosses, chests, signboards, Korok kinds)
    log('Reading placement data…')
    rx = re.compile(r'Banc/(MainField|MinusField)/([A-J]-\d_(Static|Dynamic)|Sky/.*|Cave/.*|DeepHole/.*|LargeDungeon/.*|Castle/.*)\.bcett\.byml\.zs$')
    korok_kind, seen = {}, set()
    bool_flags = {x['Hash'] for x in (gamefiles.byml(rf.read(rf.find('GameData/GameDataList.Product.', '.byml.zs')[-1]))['Data'].get('Bool') or [])}
    treasure_maps = {}
    pouch = gamefiles.byml(rf.read(rf.find('RSDB/PouchActorInfo.', '.byml.zs')[-1]))
    for row in pouch:
        if row.get('TreasureMapContent'):
            treasure_maps[row['__RowId']] = basename(row['TreasureMapContent'])
    for path in rf.find('Banc/'):
        if not rx.match(path):
            continue
        for a in (gamefiles.byml(rf.read(path)) or {}).get('Actors') or []:
            g, h, t = a.get('Gyaml') or '', a.get('Hash'), a.get('Translate')
            if not h or not t or h in seen:
                continue
            if g in KOROK_TYPES:
                korok_kind[h] = g
            if g.startswith('Enemy_'):
                kind = g.split('_')[1]
                if kind in BOSSES and mmh3(f'IsDefeatBossEnemy.{h}') in bool_flags:
                    seen.add(h)
                    data[BOSSES[kind]].append({'completion_hash': mmh3(f'IsDefeatBossEnemy.{h}'), 'position': pos(t), 'actor': g})
            elif g == 'Npc_CraftSignboard001':
                seen.add(h)
                data['addison_signposts'].append({'guid_hash': str(h), 'position': pos(t)})
            elif g.startswith('TBox_'):
                drop = (a.get('Dynamic') or {}).get('Drop__DropActor', '')
                if drop == 'Obj_SageWill':
                    seen.add(h)
                    data['sages_wills'].append({'guid_hash': str(h), 'position': pos(t)})
                elif drop in treasure_maps:
                    seen.add(h)
                    data['old_maps'].append({'completion_hash': mmh3(f'IsFindTreasureMap.{treasure_maps[drop]}'),
                                             'position': pos(t), 'display_name': f'Old map ({drop[-2:]})'})
                elif drop.startswith('Obj_AutoBuilderDraftAssassin_'):
                    seen.add(h)
                    data['yiga_schematics'].append({'completion_hash': mmh3(f'ReadyMadeAutoBuilderDraft.{drop}.IsOwned'),
                                                    'display_name': drafts.get(f'{drop}_Name', drop), 'position': pos(t)})

    for iid, t in (hk.get('HiddenKorok') or {}).items():
        kind = korok_kind.get(int(iid), '')
        data['hidden_koroks'].append({'completion_hash': mmh3(f'IsAppearKorok.{iid}'), 'position': pos(t),
                                      'type': KOROK_TYPES.get(kind, 'Korok seed'), 'internalHash': hex(int(iid))})
    for iid, t in (hk.get('CarryKorok') or {}).items():
        data['carry_koroks'].append({'completion_hash': mmh3(f'KorokCarryProgress.{iid}'), 'position': pos(t),
                                     'type': 'Korok Friends', 'internalHash': hex(int(iid))})

    for draft, site in SCHEMA_SITES.items():
        if site in places:
            data['schema_stones'].append({'completion_hash': mmh3(f'ReadyMadeAutoBuilderDraft.{draft}.IsOwned'),
                                          'display_name': drafts.get(f'{draft}_Name', draft), 'position': pos(places[site])})

    write(data, out)
    counts = {k: len(v) for k, v in data.items()}
    log(f'map data: {counts}')
    return counts


def write(data, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.part')
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(out)


def merge_reference(data, ref):
    """Add what the game files don't spell out from lud99/totk-unexplored's map_data.json:
    Korok puzzle types and routes, and the few map features without an index (Bargainer Statues,
    Great Fairies, forge constructs, ...). Matched by save flag. Returns how many entries were enriched."""
    n = 0
    for key in ('hidden_koroks', 'carry_koroks'):
        by_flag = {o['completion_hash']: o for o in ref.get(key, [])}
        for o in data.get(key, []):
            r = by_flag.get(o['completion_hash'])
            if r:
                o['type'] = r.get('type', o.get('type'))
                if r.get('path'):
                    o['path'] = r['path']
                n += 1
    for key in ('locations', 'bubbuls'):
        have = {o['completion_hash'] for o in data.get(key, [])}
        for r in ref.get(key, []):
            if r['completion_hash'] not in have:
                data[key].append(r)
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--romfs', required=True)
    ap.add_argument('--out', default=str(OUT))
    ap.add_argument('--lang', default='USen')
    args = ap.parse_args()
    if not (Path(args.romfs) / 'index.json').is_file():
        sys.exit('Not a TotK Recomp romfs folder (no index.json).')
    build(args.romfs, args.out, args.lang)


if __name__ == '__main__':
    main()
