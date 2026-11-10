"""Build assets/map_data.json (collectibles, places, bosses) from your own TotK Recomp game files.

    python build_mapdata.py [--romfs <TotK Recomp install>\\romfs] [--lang USen]

Everything comes from the game's own indexes and placement data:
- Banc/<Field>/LocationArea: shrines, lightroots, caves (+ Bubbul frogs), wells, chasms, named places
- Banc/MainField/HiddenKorok: Korok seeds and Korok friends (by instance ID); the puzzle type is the Korok
  actor's HideType, routes come from the puzzle actors (flowers, race start blocks, Korok friends' pairs)
- Banc/<Field>/<section>_Static|Dynamic, Sky, Cave, DeepHole: bosses and Lynels, treasure chests (by what's
  inside: Sage's Wills, old maps, Yiga schematics, armor, the rest), Addison's signboards, the Dragon Tears
  and the Great Fairies
- RSDB/PouchActorInfo: which armor an old map leads to; Banc/MinusField/TreasureMap
- Mals/<lang>: names
Save flags are murmur3 hashes of '<Prefix>.<instance ID or name>' (see docs/PROGRESS.md); the flag names of
the Dragon Tears (Complete_DragonTearsNN), Skyview Towers (IsOpenCannon.TowerNN) and Great Fairies
(IsAppear_DressFairy_NN) are the ones the game's event flows set. Opened chests are in the save's GUID list.
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
KOROK_ACTORS = ('Npc_HiddenKorokFly', 'Npc_HiddenKorokGround')
# Korok puzzle by the Korok actor's Dynamic.HideType (no HideType: a Korok under a liftable rock).
# 10 is both acorn puzzles: with a vine-held pot nearby it's the acorn in a hole.
HIDE_TYPES = {
    None: 'Lift the rock', 1: 'Glowing light', 2: 'Dive through the light', 3: 'Flower trail', 4: 'Race to the goal',
    5: 'Moving light', 6: 'Complete the rock pattern', 7: 'Offering plate', 8: 'Pinwheel balloons',
    9: 'Shoot the balloon', 10: 'Hanging acorn', 11: 'Land on the target', 12: 'Provide shelter',
    13: 'Repair the roof', 15: 'Block puzzle', 17: 'Catch the light', 18: 'Touch the target', 19: 'Catch the seed',
    20: 'Pull the plug', 23: 'Through the roof', 24: 'Boulder stand', 25: 'Ring the bell',
}
# LocationArea categories shown as named places (the ones discovered by visiting); shops, districts,
# small spots and towers are left out.
# Places that have no LocationArea entry but a map label (LocationMarker actor) and a visit flag:
# Bargainer Statues, Forge Constructs and the Smithing Construct.
MARKER_PLACES = re.compile(r'^(DemonStatue_\d+|SmallDemonStatue|SmeltShopGolem_\d+|ForgeShopGolem)$')
PLACE_CATEGORIES = re.compile(r'^(City|Dungeon|SkyArchipelago|Stable|SpotBig.*|SpotMiddle\w+)$')
DATA_KEYS = ['shrines', 'lightroots', 'hidden_koroks', 'carry_koroks', 'bubbuls', 'locations', 'caves', 'wells', 'chasms',
             'skyview_towers', 'great_fairies', 'hinoxes', 'taluses', 'moldugas', 'flux_constructs', 'froxes', 'gleeoks',
             'lynels', 'old_maps', 'sages_wills', 'addison_signposts', 'schema_stones', 'yiga_schematics', 'dragon_tears',
             'armor_chests', 'treasure_chests']


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
    items = msgs('ActorMsg/PouchContent')
    npcs = msgs('ActorMsg/Npc')
    creatures = msgs('ActorMsg/PictureBook')
    data = {k: [] for k in DATA_KEYS}

    def item_name(actor):
        """In-game name of a chest's content: 'Royal Guard Cap', 'Diamond', 'Arrow x 5', ..."""
        parts = actor.split('_')
        while parts:
            n = items.get('_'.join(parts) + '_Name')
            if n:
                return n
            parts.pop()
        return ''

    # ---- places, from the game's location index
    log('Reading the location index…')
    places, tear_areas = {}, {}
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
                elif cat == 'Tower':   # activated: its launch pad (cannon) is open
                    data['skyview_towers'].append({'internal_name': name, 'display_name': display,
                                                   'completion_hash': mmh3(f'IsOpenCannon.{name}'), 'position': pos(trans[0])})
                elif cat == 'DragonTears':   # the geoglyph; the tear's exact spot comes from its actor below
                    tear_areas[name] = (names.get(name) or f"Dragon's Tear {int(name[-2:])}" if name[-2:].isdigit() else display,
                                        trans[0])
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
    flowers, start_blocks, landing_blocks, vine_pots, carry, markers, frogs = [], [], [], [], {}, {}, {}
    tears, fairies = [], {}
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
            if g in KOROK_ACTORS:
                korok_kind[h] = (g, (a.get('Dynamic') or {}).get('HideType'))
            elif g == 'Obj_Plant_Korok_A_01':
                flowers.append((t, (a.get('Dynamic') or {}).get('TrackingFlowerType')))
            elif g.startswith('Enemy_CaveMaster'):   # Bubbul frog; LocationName = its cave
                frogs.setdefault((a.get('Dynamic') or {}).get('LocationName', ''), t)
            elif g == 'LocationMarker':
                loc = (a.get('Dynamic') or {}).get('Location', '')
                if MARKER_PLACES.match(loc):
                    markers.setdefault(loc, t)
            elif g == 'FldObj_KorokStartingBlock_A_01':
                start_blocks.append(t)
            elif g == 'FldObj_KorokGoalBlock_A_02':
                landing_blocks.append(t)
            elif g == 'Obj_KorokPotFixedVine_A_01':
                vine_pots.append(t)
            elif g in ('KorokCarry_Destination', 'KorokCarryPassenger_Pair'):
                carry[h] = (g, t, [l.get('Dst') for l in a.get('Links') or []])
            elif g == 'FldObj_DragonTears_01':
                tears.append(t)
            elif re.match(r'Npc_DressFairy_\d\d$', g):
                fairies.setdefault(g, t)
            if g.startswith('Enemy_Lynel'):
                # Lynels come back with every Blood Moon and their defeat flag resets with them, so only where they are
                seen.add(h)
                data['lynels'].append({'display_name': creatures.get(g.replace('_Boss', '') + '_Name') or 'Lynel',
                                       'position': pos(t), 'actor': g})
            elif g.startswith('Enemy_'):
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
                else:   # every other chest; opened chests are in the save's GUID list
                    seen.add(h)
                    key = 'armor_chests' if drop.startswith('Armor_') else 'treasure_chests'
                    data[key].append({'guid_hash': str(h), 'position': pos(t),
                                      'display_name': item_name(drop) or ('Armor' if key == 'armor_chests' else 'Treasure chest')})

    trails = flower_trails(flowers)
    pairs = carry_routes(carry)
    for iid, t in (hk.get('HiddenKorok') or {}).items():
        _, hide = korok_kind.get(int(iid), ('', None))
        o = {'completion_hash': mmh3(f'IsAppearKorok.{iid}'), 'position': pos(t),
             'type': HIDE_TYPES.get(hide, 'Korok seed'), 'internalHash': hex(int(iid))}
        if hide == 10 and _nearest(vine_pots, t, 30):
            o['type'] = 'Acorn in a hole'
        elif hide == 3 and trails:   # the trail whose last flower is next to the Korok
            trail = min(trails, key=lambda tr: _dist(tr[-1], t))
            o['path'] = {'flowers': [{'position': pos(f)} for f in trail]}
        elif hide == 4 and start_blocks:   # race: from the start block to the goal ring at the Korok
            o['path'] = {'start': pos(_nearest(start_blocks, t)), 'end': pos(t)}
        elif hide == 11 and start_blocks and landing_blocks:   # glide from the start block onto the target
            o['path'] = {'start': pos(_nearest(start_blocks, t)), 'end': pos(_nearest(landing_blocks, t))}
        data['hidden_koroks'].append(o)
    for iid, t in (hk.get('CarryKorok') or {}).items():   # t = where the pair has to be taken
        o = {'completion_hash': mmh3(f'KorokCarryProgress.{iid}'), 'position': pos(t),
             'type': 'Korok friends', 'internalHash': hex(int(iid))}
        start = min(pairs, key=lambda p: _dist(p[1], t)) if pairs else None
        if start and _dist(start[1], t) < 5:
            o['path'] = {'start': pos(start[0]), 'end': pos(t)}
        data['carry_koroks'].append(o)

    # Bubbul frogs in places without a cave map marker (the Ancient Zora Waterworks): at the frog itself
    known = {o['internal_name'] for o in data['bubbuls']}
    for loc, t in sorted(frogs.items()):
        flag = mmh3(f'IsGetCaveMasterMedal.{loc}')
        if loc and loc not in known and flag in bool_flags:
            data['bubbuls'].append({'internal_name': loc, 'display_name': names.get(loc, loc),
                                    'completion_hash': flag, 'position': pos(t)})

    shown = {o['completion_hash'] for o in data['locations']}
    for loc, t in sorted(markers.items()):
        flag = mmh3(f'IsVisitLocation.{loc}')
        if flag in bool_flags and flag not in shown:
            data['locations'].append({'display_name': names.get(loc, loc), 'completion_hash': flag, 'position': pos(t)})

    # Dragon Tears: the tear actor inside each geoglyph (memory watched = Complete_DragonTearsNN)
    for name, (display, t) in sorted(tear_areas.items()):
        flag = mmh3(f'Complete_{name}')
        if flag in bool_flags:
            spot = _nearest(tears, t, 600) or t
            data['dragon_tears'].append({'internal_name': name, 'display_name': display, 'completion_hash': flag,
                                         'position': pos(spot)})

    # Great Fairies: revived = IsAppear_DressFairy_NN; at the fairy's fountain
    for g, t in sorted(fairies.items()):
        flag = mmh3(f'IsAppear_{g[4:]}')
        if flag in bool_flags:
            data['great_fairies'].append({'display_name': npcs.get(f'{g}_Name', 'Great Fairy'), 'completion_hash': flag,
                                          'position': pos(t)})

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


def _dist(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5


def _nearest(points, t, within=None):
    best = min(points, key=lambda p: _dist(p, t), default=None)
    return best if best is not None and (within is None or _dist(best, t) <= within) else None


def flower_trails(flowers, link=60):
    """Group the Korok trail flowers into trails (flowers closer than `link` to each other) and order each
    from its first flower (TrackingFlowerType 1) to the next nearest, ending at the last (type 2)."""
    n = len(flowers)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(n):
        for j in range(i + 1, n):
            if _dist(flowers[i][0], flowers[j][0]) < link:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    trails = []
    for idx in groups.values():
        first = [i for i in idx if flowers[i][1] == 1]
        cur = first[0] if first else idx[0]
        order, rest = [cur], set(idx) - {cur}
        while rest:
            cur = min(rest, key=lambda i: _dist(flowers[i][0], flowers[cur][0]))
            order.append(cur)
            rest.remove(cur)
        trails.append([flowers[i][0] for i in order])
    return trails


def carry_routes(carry):
    """[(start, destination)] for Korok friends: KorokCarryPassenger_Pair (where they wait) links to its
    KorokCarry_Destination (where the partner is)."""
    out = []
    for g, t, links in carry.values():
        if g != 'KorokCarryPassenger_Pair':
            continue
        for d in links:
            dest = carry.get(d)
            if dest and dest[0] == 'KorokCarry_Destination':
                out.append((t, dest[1]))
                break
    return out


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
