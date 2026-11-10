"""Read a Tears of the Kingdom progress.sav and work out which map objects are done.

The save starts with a table of (u32 hash, u32 value) pairs from offset 0x28. It ends at the
MetaData.SaveTypeHash entry, whose value is the offset of a u64 GUID array (ends with 0).
Most objects are matched by their completion hash in the table; Sage's Wills and Addison's
signposts are matched by GUID instead.
"""
import struct
from pathlib import Path

HEADER_MAGIC = 0x01020304
TABLE_START = 0x28
SAVE_TYPE_HASH = 0xA3DB7114   # MetaData.SaveTypeHash: end of the hash table
PLAYTIME_HASH = 0xE573F564
STATUS_CLEAR = 1654019904     # 'Clear': shrine done, Korok friends reunited
STATUS_OPEN = 404286466       # 'Open': lightroot activated; shrine found (its door opened)
STATUS_ENTER = 2121473774     # 'Enter': shrine entered, not finished

# category key -> (map_data.json key, how it is completed)
CATEGORIES = {
    'hidden_korok':   ('hidden_koroks', 'nonzero'),
    'carry_korok':    ('carry_koroks', 'clear'),
    'shrine':         ('shrines', 'clear'),
    'lightroot':      ('lightroots', 'open'),
    'cave':           ('caves', 'nonzero'),
    'bubbul':         ('bubbuls', 'nonzero'),
    'well':           ('wells', 'nonzero'),
    'chasm':          ('chasms', 'nonzero'),
    'location':       ('locations', 'nonzero'),
    'skyview_tower':  ('skyview_towers', 'nonzero'),
    'great_fairy':    ('great_fairies', 'nonzero'),
    'hinox':          ('hinoxes', 'nonzero'),
    'talus':          ('taluses', 'nonzero'),
    'molduga':        ('moldugas', 'nonzero'),
    'flux_construct': ('flux_constructs', 'nonzero'),
    'frox':           ('froxes', 'nonzero'),
    'gleeok':         ('gleeoks', 'nonzero'),
    'lynel':          ('lynels', 'none'),     # not tracked: Lynels come back after a Blood Moon
    'sages_will':     ('sages_wills', 'guid'),
    'old_map':        ('old_maps', 'nonzero'),
    'addison_sign':   ('addison_signposts', 'guid'),
    'schema_stone':   ('schema_stones', 'nonzero'),
    'yiga_schematic': ('yiga_schematics', 'nonzero'),
    'dragon_tear':    ('dragon_tears', 'nonzero'),
    'armor_chest':    ('armor_chests', 'guid'),
    'treasure_chest': ('treasure_chests', 'guid'),
}


class SaveError(Exception):
    pass


def mmh3(text, seed=0):
    """MurmurHash3 x86 32-bit: the game hashes flag names and enum values with it."""
    key = text.encode('utf-8')
    h = seed
    c1, c2 = 0xCC9E2D51, 0x1B873593
    n = len(key) // 4
    for i in range(n):
        k = struct.unpack_from('<I', key, i * 4)[0]
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
        h = ((h << 13) | (h >> 19)) & 0xFFFFFFFF
        h = (h * 5 + 0xE6546B64) & 0xFFFFFFFF
    tail = key[n * 4:]
    k = 0
    if len(tail) >= 3:
        k ^= tail[2] << 16
    if len(tail) >= 2:
        k ^= tail[1] << 8
    if tail:
        k ^= tail[0]
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
    h ^= len(key)
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    h ^= h >> 16
    return h


STEP_NOT_READY = mmh3('NotReady')
STEP_READY = mmh3('Ready')
STEP_COMPLETE = mmh3('Complete')


def _and(a, b):
    return False if a is False or b is False else (None if a is None or b is None else True)


def _or(a, b):
    return True if a is True or b is True else (None if a is None or b is None else False)


def evaluate(h, table, logic, cache):
    """Run the game's BoolExp program `h` (postfix) against the save. True / False / None (unknown).

    Opcodes: 0 GetBool, 10 another BoolExp, 1/12 then 2: enum == / > value (by enum order),
    3 AND, 4 OR, 5 NOT. Anything else (bool arrays, ...) counts as unknown.
    """
    key = str(h)
    if key in cache:
        return cache[key]
    prog = logic['exprs'].get(key)
    if prog is None:
        return None
    cache[key] = None  # guard against cycles
    stack, pending = [], None
    for ins in prog:
        op, arg = ins[0], (ins[1] if len(ins) > 1 else None)
        if op == 0:
            v = table.get(arg)
            if v is None:
                d = logic['bools'].get(str(arg))
                stack.append(None if d is None else bool(d))
            else:
                stack.append(v != 0)
        elif op == 10:
            stack.append(evaluate(arg, table, logic, cache))
        elif op in (1, 12):
            pending = (op, arg)
        elif op == 2 and pending:
            kind, enum = pending
            pending = None
            info = logic['enums'].get(str(enum))
            cur = table.get(enum, info['default'] if info else None)
            if cur is None:
                stack.append(None)
            elif kind == 1:
                stack.append(cur == arg)
            else:
                order = info['order'] if info else []
                stack.append(order.index(cur) > order.index(arg) if cur in order and arg in order else None)
        elif op in (3, 4) and len(stack) >= 2:
            b, a = stack.pop(), stack.pop()
            stack.append(_and(a, b) if op == 3 else _or(a, b))
        elif op == 5 and stack:
            v = stack.pop()
            stack.append(None if v is None else not v)
        else:
            stack.append(None)
    result = stack[-1] if stack else None
    cache[key] = result
    return result


def parse_quests(path, quests, logic=None):
    """{quest id: [status, current step name, can start]}; status is locked / available / active / done.

    Each quest has an enum flag Step_<id> whose value is the murmur3 hash of the current step name.
    For available quests, `can start` is the quest's prerequisite (DependFlagName) evaluated against
    the save: True, False, or None when the game data can't tell.
    """
    buf = Path(path).read_bytes()
    table, _ = read_table(buf)
    cache = {}
    out = {}
    for q in quests:
        v = table.get(q['flag'])
        if v is None or v == STEP_NOT_READY:
            out[q['id']] = ['locked', 'NotReady', False]
        elif v == STEP_READY:
            req = q.get('requires')
            if not req:
                can = True
            elif req['kind'] == 'bool':
                b = table.get(req['hash'])
                can = (b != 0) if b is not None else bool((logic or {}).get('bools', {}).get(str(req['hash'])))
            elif req['kind'] == 'exp' and logic:
                can = evaluate(req['hash'], table, logic, cache)
            else:
                can = None
            out[q['id']] = ['available', 'Ready', can]
        elif v == STEP_COMPLETE:
            out[q['id']] = ['done', 'Complete', None]
        else:
            name = next((s['name'] for s in q['steps'] if s['hash'] == v), f'0x{v:08x}')
            out[q['id']] = ['active', name, None]
    return out


def _check(buf):
    if len(buf) < TABLE_START + 8 or struct.unpack_from('<I', buf, 0)[0] != HEADER_MAGIC:
        raise SaveError('not a TotK progress.sav (bad header)')


def read_table(buf):
    """Return ({hash: value}, guid_array_offset). The first entry of a hash wins."""
    _check(buf)
    table = {}
    guid_offset = None
    end = len(buf) - 8
    for off in range(TABLE_START, end + 1, 8):
        h, v = struct.unpack_from('<II', buf, off)
        if h == SAVE_TYPE_HASH:
            guid_offset = v
            break
        table.setdefault(h, v)
    if guid_offset is None:
        raise SaveError('hash table end (SaveTypeHash) not found')
    return table, guid_offset


def read_guids(buf, offset):
    guids = set()
    if not 0 < offset < len(buf):
        return guids
    for off in range(offset, len(buf) - 7, 8):
        g = struct.unpack_from('<Q', buf, off)[0]
        if g == 0:
            break
        guids.add(g)
    return guids


SAVE_POS_HASH = mmh3('PlayerStatus.SavePos')


def player_position(buf, table):
    """Where Link was when the game saved: Vector3 `PlayerStatus.SavePos` (the table value is the offset
    of three floats). None when the save doesn't have it."""
    off = table.get(SAVE_POS_HASH)
    if off is None or not 0 < off <= len(buf) - 12:
        return None
    x, y, z = struct.unpack_from('<3f', buf, off)
    if not all(abs(v) < 20000 for v in (x, y, z)) or (x, y, z) == (0, 0, 0):
        return None
    return {'x': round(x, 1), 'y': round(y, 1), 'z': round(z, 1)}


def save_info(path):
    """Version id and play time (seconds) of a progress.sav, without full parsing."""
    buf = Path(path).read_bytes()
    table, _ = read_table(buf)
    return {
        'version_id': struct.unpack_from('<I', buf, 4)[0],
        'playtime': table.get(PLAYTIME_HASH, 0),
    }


def parse(path, map_data):
    """Return {category: [bool done per object, in map_data order]} plus metadata."""
    buf = Path(path).read_bytes()
    table, guid_offset = read_table(buf)
    guids = read_guids(buf, guid_offset)

    done = {}
    for cat, (key, rule) in CATEGORIES.items():
        flags = []
        for obj in map_data.get(key, []):
            if rule == 'guid':
                flags.append(int(obj['guid_hash']) in guids)
                continue
            if rule == 'none':
                flags.append(False)
                continue
            status = table.get(obj['completion_hash'])
            if status is None:
                flags.append(False)
            elif rule == 'clear':
                flags.append(status == STATUS_CLEAR)
            elif rule == 'open':
                flags.append(status == STATUS_OPEN)
            else:
                flags.append(status != 0)
        done[cat] = flags

    # shrines found (door opened or entered) but not finished yet
    found = {'shrine': [table.get(o['completion_hash']) in (STATUS_OPEN, STATUS_ENTER) for o in map_data.get('shrines', [])]}

    return {
        'version_id': struct.unpack_from('<I', buf, 4)[0],
        'playtime': table.get(PLAYTIME_HASH, 0),
        'player': player_position(buf, table),
        'done': done,
        'found': found,
    }
