"""Minimal readers for TotK game files: TotK Recomp romfs.bin, .zs (zstd + dictionaries), SARC, MSBT, BYML."""
import json
import struct
from pathlib import Path

import zstandard


class Romfs:
    """TotK Recomp keeps the romfs as one romfs.bin plus index.json (path, offset, size)."""

    def __init__(self, folder):
        self.folder = Path(folder)
        index = json.loads((self.folder / 'index.json').read_text(encoding='utf-8'))
        self.files = {f['path']: (f['offset'], f['size']) for f in index['files']}
        self._dicts = None

    def raw(self, path):
        off, size = self.files[path]
        with open(self.folder / 'romfs.bin', 'rb') as f:
            f.seek(off)
            return f.read(size)

    def find(self, prefix, suffix=''):
        return sorted(p for p in self.files if p.startswith(prefix) and p.endswith(suffix))

    def dicts(self):
        if self._dicts is None:
            pack = sarc(zstandard.ZstdDecompressor().decompress(self.raw('Pack/ZsDic.pack.zs'), max_output_size=1 << 26))
            self._dicts = {n: zstandard.ZstdCompressionDict(d) for n, d in pack.items()}
        return self._dicts

    def read(self, path):
        data = self.raw(path)
        if not path.endswith('.zs'):
            return data
        if path.endswith('.pack.zs'):
            d = self.dicts().get('pack.zsdic')
        elif path.endswith('.bcett.byml.zs'):
            d = self.dicts().get('bcett.byml.zsdic')
        else:
            d = self.dicts().get('zs.zsdic')
        for dic in (d, None):
            try:
                dz = zstandard.ZstdDecompressor(dict_data=dic) if dic else zstandard.ZstdDecompressor()
                return dz.decompress(data, max_output_size=1 << 28)
            except zstandard.ZstdError:
                continue
        raise ValueError(f'cannot decompress {path}')


def sarc(data):
    """{name: bytes} of a SARC archive (little endian)."""
    assert data[:4] == b'SARC', 'not a SARC'
    bom = data[6:8]
    e = '<' if bom == b'\xff\xfe' else '>'
    data_start = struct.unpack_from(e + 'I', data, 0x0C)[0]
    sfat = 0x14
    count = struct.unpack_from(e + 'H', data, sfat + 6)[0]
    nodes = [struct.unpack_from(e + 'IIII', data, sfat + 12 + i * 16) for i in range(count)]
    sfnt = sfat + 12 + count * 16
    names_start = sfnt + 8
    out = {}
    for _hash, attr, start, end in nodes:
        if attr & 0x01000000:
            name_off = (attr & 0xFFFF) * 4
            name = data[names_start + name_off:data.index(b'\0', names_start + name_off)].decode('utf-8')
        else:
            name = f'{_hash:08x}'
        out[name] = data[data_start + start:data_start + end]
    return out


def _clean_msbt_text(raw):
    """UTF-16LE text with control tags (0x0E group type size data, 0x0F close) removed."""
    out = []
    i = 0
    n = len(raw) // 2
    chars = struct.unpack(f'<{n}H', raw[:n * 2])
    while i < n:
        c = chars[i]
        if c == 0:
            break
        if c == 0x0E:  # tag: group, type, size(bytes), params
            size = chars[i + 3] if i + 3 < n else 0
            i += 4 + size // 2
            continue
        if c == 0x0F:  # closing tag: group, type
            i += 3
            continue
        out.append(chr(c))
        i += 1
    return ''.join(out)


def msbt(data):
    """{label: text} of an MSBT message file."""
    assert data[:8] == b'MsgStdBn', 'not MSBT'
    e = '<' if data[8:10] == b'\xff\xfe' else '>'
    sections = struct.unpack_from(e + 'H', data, 0x0E)[0]
    off = 0x20
    labels, texts = {}, []
    for _ in range(sections):
        magic = data[off:off + 4]
        size = struct.unpack_from(e + 'I', data, off + 4)[0]
        body = off + 16
        if magic == b'LBL1':
            groups = struct.unpack_from(e + 'I', data, body)[0]
            for g in range(groups):
                cnt, loff = struct.unpack_from(e + 'II', data, body + 4 + g * 8)
                p = body + loff
                for _ in range(cnt):
                    ln = data[p]
                    name = data[p + 1:p + 1 + ln].decode('utf-8')
                    idx = struct.unpack_from(e + 'I', data, p + 1 + ln)[0]
                    labels[name] = idx
                    p += 1 + ln + 4
        elif magic == b'TXT2':
            cnt = struct.unpack_from(e + 'I', data, body)[0]
            offs = [struct.unpack_from(e + 'I', data, body + 4 + i * 4)[0] for i in range(cnt)] + [size]
            texts = [_clean_msbt_text(data[body + offs[i]:body + offs[i + 1]]) for i in range(cnt)]
        off = body + size
        off = (off + 15) & ~15
    return {name: texts[idx] for name, idx in labels.items() if idx < len(texts)}


def byml(data):
    """Parse a BYML (v2-v7) document into Python objects. Hash keys stay as strings."""
    e = '<' if data[:2] == b'YB' else '>'
    _ver, key_off, str_off, root_off = struct.unpack_from(e + 'HIII', data, 2)

    def strtab(off):
        if not off:
            return []
        cnt = int.from_bytes(data[off + 1:off + 4], 'little' if e == '<' else 'big')
        offs = struct.unpack_from(e + f'{cnt}I', data, off + 4)
        return [data[off + o:data.index(b'\0', off + o)].decode('utf-8') for o in offs]

    keys, strings = strtab(key_off), strtab(str_off)

    def value(t, raw):
        if t == 0xA0:
            return strings[raw]
        if t == 0xD0:
            return bool(raw)
        if t == 0xD1:
            return struct.unpack(e + 'i', struct.pack(e + 'I', raw))[0]
        if t == 0xD2:
            return struct.unpack(e + 'f', struct.pack(e + 'I', raw))[0]
        if t == 0xD3:
            return raw
        if t in (0xD4, 0xD5, 0xD6):
            return struct.unpack_from(e + {0xD4: 'q', 0xD5: 'Q', 0xD6: 'd'}[t], data, raw)[0]
        if t == 0xFF:
            return None
        if t in (0xC0, 0xC1, 0x20, 0x21):
            return node(raw)
        return raw

    def node(off):
        t = data[off]
        cnt = int.from_bytes(data[off + 1:off + 4], 'little' if e == '<' else 'big')
        if t == 0xC0:  # array
            types = data[off + 4:off + 4 + cnt]
            vals = off + 4 + ((cnt + 3) & ~3)
            return [value(types[i], struct.unpack_from(e + 'I', data, vals + i * 4)[0]) for i in range(cnt)]
        if t == 0xC1:  # dict
            out = {}
            for i in range(cnt):
                p = off + 4 + i * 8
                k = int.from_bytes(data[p:p + 3], 'little' if e == '<' else 'big')
                vt = data[p + 3]
                out[keys[k]] = value(vt, struct.unpack_from(e + 'I', data, p + 4)[0])
            return out
        raise ValueError(f'unsupported BYML node 0x{t:02x}')

    return node(root_off) if root_off else None
