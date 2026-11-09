"""Build assets/quests.json from your own TotK Recomp game files (romfs.bin + index.json).

    python build_quests.py [--romfs <TotK Recomp install>\\romfs] [--lang USen]

Reads RSDB/Challenge (quest list, type, steps, destinations) and Mals/<lang> (quest names and the
adventure log text of each step, quest giver and region names). Needs: pip install zstandard
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import gamefiles
from paths import ASSETS
from savefile import mmh3

OUT = ASSETS / 'quests.json'
DEFAULT_ROMFS = ([Path(os.environ['TOTK_DIR']) / 'romfs'] if os.environ.get('TOTK_DIR') else []) + \
    [Path(f'{d}:/Games/TotK/romfs') for d in 'CDEFG'] + [Path.home() / 'Games' / 'TotK' / 'romfs']

CATEGORY = {'Main': 'main', 'ImportantMini': 'side_adventure', 'Sub': 'shrine', None: 'side_quest'}


def basename(path):
    """'Work/Actor/Npc_oasis012.engine__actor__ActorParam.gyml' -> 'Npc_oasis012'"""
    return path.rsplit('/', 1)[-1].split('.', 1)[0] if path else ''


def points(dest):
    """All X/Y/Z positions inside a step's DestinationPoint list."""
    found = []

    def walk(o):
        if isinstance(o, dict):
            if {'X', 'Y', 'Z'} <= o.keys():
                found.append([round(o['X'], 1), round(o['Y'], 1), round(o['Z'], 1)])
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(dest)
    uniq = []
    for p in found:
        if p not in uniq:
            uniq.append(p)
    return uniq


def tidy(text):
    return re.sub(r'\n{3,}', '\n\n', text.replace('\r', '')).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--romfs')
    ap.add_argument('--lang', default='USen')
    args = ap.parse_args()

    romfs = Path(args.romfs) if args.romfs else next((p for p in DEFAULT_ROMFS if (p / 'index.json').exists()), None)
    if not romfs or not (romfs / 'index.json').exists():
        sys.exit('TotK Recomp romfs folder not found. Pass --romfs <install folder>\\romfs.')
    print(build(romfs, OUT, args.lang))


def build(romfs, out=OUT, lang='USen', log=print):
    """Read the quest table, messages and game data from `romfs` and write `out`. Returns a summary line."""
    rf = gamefiles.Romfs(romfs)

    table_path = rf.find('RSDB/Challenge.Product.', '.rstbl.byml.zs')[-1]
    mals_path = rf.find(f'Mals/{lang}.Product.', '.sarc.zs')[-1]
    log(f'Reading {table_path} and {mals_path}')
    rows = gamefiles.byml(rf.read(table_path))
    mals = gamefiles.sarc(rf.read(mals_path))

    def msgs(name):
        f = f'{name}.msbt'
        return gamefiles.msbt(mals[f]) if f in mals else {}

    npc_names = msgs('ActorMsg/Npc')
    loc_names = {**msgs('LocationMsg/Location'), **msgs('LocationMsg/Dungeon')}

    # Game data: flag defaults, enum value order and the boolean expressions behind quest prerequisites
    gd_path = rf.find('GameData/GameDataList.Product.', '.byml.zs')[-1]
    log(f'Reading {gd_path}')
    gd = gamefiles.byml(rf.read(gd_path))['Data']
    bool_def = {x['Hash']: int(bool(x.get('DefaultValue', 0))) for x in gd.get('Bool', [])}
    enum_def = {x['Hash']: {'order': list(x['Values']), 'default': x.get('DefaultValue')} for x in gd.get('Enum', [])}
    exp_def = {x['Hash']: [list(i) for i in x['Values']] for x in gd.get('BoolExp', [])}
    step_enum_to_quest = {mmh3(f'Step_{basename(r["__RowId"])}'): basename(r['__RowId']) for r in rows}
    logic = {'exprs': {}, 'bools': {}, 'enums': {}}

    def collect(h, seen_quests):
        """Copy expression h and everything it reads into `logic`; note which quests' steps it checks."""
        if str(h) in logic['exprs'] or h not in exp_def:
            return
        prog = exp_def[h]
        logic['exprs'][str(h)] = prog
        for ins in prog:
            op, arg = ins[0], (ins[1] if len(ins) > 1 else None)
            if op == 0 and arg in bool_def:
                logic['bools'][str(arg)] = bool_def[arg]
            elif op in (1, 12) and arg in enum_def:
                logic['enums'][str(arg)] = enum_def[arg]
                if arg in step_enum_to_quest:
                    seen_quests.add(step_enum_to_quest[arg])
            elif op == 10:
                collect(arg, seen_quests)

    def requirement(flag_name):
        h = mmh3(flag_name)
        needs = set()
        if h in exp_def:
            collect(h, needs)
            # an expression already collected earlier: still find the quests it checks
            stack, seen = [h], set()
            while stack:
                e = stack.pop()
                if e in seen:
                    continue
                seen.add(e)
                for ins in exp_def.get(e, []):
                    if ins[0] in (1, 12) and len(ins) > 1 and ins[1] in step_enum_to_quest:
                        needs.add(step_enum_to_quest[ins[1]])
                    elif ins[0] == 10 and len(ins) > 1:
                        stack.append(ins[1])
            return {'kind': 'exp', 'hash': h, 'name': flag_name, 'quests': sorted(needs)}
        if h in bool_def:
            logic['bools'][str(h)] = bool_def[h]
            return {'kind': 'bool', 'hash': h, 'name': flag_name, 'quests': []}
        return {'kind': 'unknown', 'hash': h, 'name': flag_name, 'quests': []}

    quests = []
    for row in rows:
        qid = basename(row['__RowId'])
        info = msgs(f'ChallengeMsg/Info_{qid}')
        if row.get('IsListAdventureLog') is False or 'Name' not in info:
            continue  # hidden mini-game bookkeeping, not in the adventure log
        giver = basename(row.get('RequestActor'))
        region = basename(row.get('RequestLocation'))
        steps = []
        for s in row['Steps']:
            steps.append({
                'name': s['Name'],
                'hash': mmh3(s['Name']),
                'text': tidy(info.get(s['Name'], '')),
                'points': points(s.get('DestinationPoint')),
            })
        if not any(s['name'] == 'Complete' for s in steps) and 'Complete' in info:
            steps.append({'name': 'Complete', 'hash': mmh3('Complete'), 'text': tidy(info['Complete']), 'points': []})

        # Where to start: the giver's own position if a step points at them, else the first located step
        giver_pts = []
        for s in row['Steps']:
            for dpt in s.get('DestinationPoint') or []:
                if isinstance(dpt, dict) and dpt.get('Actor') == row.get('RequestActor'):
                    for p in points(dpt):
                        if p not in giver_pts:
                            giver_pts.append(p)
        exact = bool(giver_pts)
        if not giver_pts:
            giver_pts = next((s['points'] for s in steps if s['points']), [])
        dep = row.get('DependFlagName')
        quests.append({
            'id': qid,
            'name': info['Name'],
            'category': CATEGORY.get(row.get('Category'), 'side_quest'),
            'sort': row.get('SortIndex', 99999),
            'giver': npc_names.get(f'{giver}_Name', ''),
            'region': loc_names.get(region, region),
            'flag': mmh3(f'Step_{qid}'),
            'giver_actor': giver,
            'start': {'points': giver_pts[:4], 'exact': exact},
            'requires': requirement(dep) if dep else None,
            'steps': steps,
        })
    quests.sort(key=lambda q: (q['category'], q['sort'], q['name']))

    # Quest series: a character (not a letter, statue or voice) gives quests that sit next to each other
    # in the adventure log one at a time, e.g. Hoz: Bring Peace to Hyrule Field! -> ... to Necluda!
    # The game decides this in dialogue scripts; log order is the inferred stand-in.
    by_actor = {}
    for q in quests:
        a = q['giver_actor'].lower()
        if a.startswith(('npc_', 'subchallnpc')):
            by_actor.setdefault(q['giver_actor'], []).append(q)
    for group in by_actor.values():
        group.sort(key=lambda q: q['sort'])
        for prev, q in zip(group, group[1:]):
            if q['sort'] - prev['sort'] == 1:
                q['after'] = prev['id']
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.part')
    tmp.write_text(json.dumps({'source': {'table': table_path, 'messages': mals_path, 'gamedata': gd_path},
                               'quests': quests, 'logic': logic},
                              ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    tmp.replace(out)
    log(f'starts: {sum(1 for q in quests if q["start"]["exact"])} exact, '
        f'{sum(1 for q in quests if q["start"]["points"] and not q["start"]["exact"])} approximate, '
        f'{sum(1 for q in quests if not q["start"]["points"])} none; '
        f'prerequisites: {sum(1 for q in quests if q["requires"])} ({len(logic["exprs"])} expressions); '
        f'in a series: {sum(1 for q in quests if q.get("after"))}')
    by = {}
    for q in quests:
        by[q['category']] = by.get(q['category'], 0) + 1
    return f'{len(quests)} quests -> {out}  {by}'


if __name__ == '__main__':
    main()
