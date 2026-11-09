"""Generate the app's own map icons (web/icons/*.svg). Drawn for this project; no game art.

    python tools/make_icons.py
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / 'web' / 'icons'

# name: (badge color, glyph SVG in a 32x32 box, glyph color)
W = '#fff8e6'
ICONS = {
    # Koroks & shrines
    'korok_hidden': ('#c98a2b', '<path d="M16 6c6 4 8 10 3 18-1 1-2 2-3 2s-2-1-3-2C8 16 10 10 16 6z"/><path d="M16 9v15" stroke="#7a4f12" stroke-width="1.6" fill="none"/>', W),
    'korok_carry': ('#c98a2b', '<path d="M11 7c4 3 5 7 2 13-1 1-2 1-3 0-3-5-2-10 1-13z"/><path d="M21 9c4 3 5 7 2 13-1 1-2 1-3 0-3-5-2-10 1-13z"/>', W),
    'shrine': ('#1f8fd1', '<path d="M16 5l9 6v15H7V11z" fill="none" stroke-width="2.4" stroke-linejoin="round"/><path d="M12 26v-7a4 4 0 0 1 8 0v7"/>', W),
    'lightroot': ('#2aa38a', '<circle cx="16" cy="12" r="5"/><path d="M16 17v9M16 22l-5 4M16 22l5 4M16 12l0 0" stroke-width="2.2" stroke-linecap="round" fill="none"/>', '#eaffd0'),
    # Places
    'cave': ('#6d5a43', '<path d="M5 25c2-11 6-17 11-17s9 6 11 17z"/><path d="M11 25c1-5 3-8 5-8s4 3 5 8z" fill="#2b2118"/>', W),
    'bubbul': ('#3f9b4a', '<ellipse cx="16" cy="19" rx="9" ry="7"/><circle cx="11" cy="11" r="3.2"/><circle cx="21" cy="11" r="3.2"/><circle cx="11" cy="11" r="1.3" fill="#1b3d1f"/><circle cx="21" cy="11" r="1.3" fill="#1b3d1f"/>', '#e9ffe0'),
    'well': ('#5f6f80', '<ellipse cx="16" cy="12" rx="9" ry="3.5" fill="none" stroke-width="2.2"/><path d="M7 12v10c0 2 4 4 9 4s9-2 9-4V12" fill="none" stroke-width="2.2"/><path d="M10 19h12" stroke-width="1.6"/>', W),
    'chasm': ('#7a2f3a', '<ellipse cx="16" cy="17" rx="10" ry="7"/><ellipse cx="16" cy="18" rx="6" ry="3.6" fill="#2a0e14"/>', '#ffb4a8'),
    'location': ('#8a7d64', '<path d="M16 5a7 7 0 0 1 7 7c0 6-7 14-7 14S9 18 9 12a7 7 0 0 1 7-7z"/><circle cx="16" cy="12" r="2.6" fill="#8a7d64"/>', W),
    # Bosses
    'hinox': ('#9a3b2e', '<ellipse cx="16" cy="16" rx="10" ry="7"/><circle cx="16" cy="16" r="4" fill="#9a3b2e"/><circle cx="16" cy="16" r="1.8"/>', W),
    'talus': ('#7d7466', '<path d="M8 24l2-9 6-6 6 4 3 11z"/><path d="M13 16l3-2 3 3" stroke="#7d7466" stroke-width="1.6" fill="none"/>', W),
    'molduga': ('#b8863b', '<path d="M4 20c4-6 8-6 12 0s8 6 12 0" fill="none" stroke-width="3" stroke-linecap="round"/><path d="M10 13l3-5 3 5" />', W),
    'flux_construct': ('#5c6fb8', '<rect x="6" y="6" width="8" height="8" rx="1"/><rect x="18" y="6" width="8" height="8" rx="1"/><rect x="12" y="18" width="8" height="8" rx="1"/>', W),
    'frox': ('#6a4c8f', '<path d="M5 22c0-7 5-12 11-12s11 5 11 12z"/><path d="M14 10l2-6 2 6" /><circle cx="12" cy="17" r="1.6" fill="#6a4c8f"/><circle cx="20" cy="17" r="1.6" fill="#6a4c8f"/>', W),
    'gleeok': ('#b03a5b', '<path d="M16 27V16M16 16l-7-8M16 16l7-8M16 16V6" stroke-width="2.6" stroke-linecap="round" fill="none"/><circle cx="9" cy="8" r="2.6"/><circle cx="23" cy="8" r="2.6"/><circle cx="16" cy="6" r="2.6"/>', W),
    # Collectibles
    'sages_will': ('#2f8f8a', '<circle cx="16" cy="16" r="5"/><path d="M16 5v4M16 23v4M5 16h4M23 16h4M8.5 8.5l2.8 2.8M20.7 20.7l2.8 2.8M8.5 23.5l2.8-2.8M20.7 11.3l2.8-2.8" stroke-width="2" stroke-linecap="round" fill="none"/>', '#e6fffb'),
    'old_map': ('#9b7a45', '<path d="M6 8l6-2 8 2 6-2v18l-6 2-8-2-6 2z"/><path d="M12 6v18M20 8v18" stroke="#9b7a45" stroke-width="1.4" fill="none"/><path d="M9 15l3 2 4-3 4 2 3-2" stroke="#b03a2e" stroke-width="1.4" fill="none"/>', W),
    'addison_sign': ('#c0532f', '<rect x="8" y="7" width="16" height="10" rx="1.5"/><path d="M16 17v9" stroke-width="2.6" stroke-linecap="round" fill="none"/><path d="M11 11h10M11 14h7" stroke="#c0532f" stroke-width="1.4" fill="none"/>', W),
    'schema_stone': ('#3d8b8f', '<path d="M9 5h14l2 22H7z"/><path d="M12 11h8M12 15h8M12 19h5" stroke="#3d8b8f" stroke-width="1.6" fill="none"/>', W),
    'yiga_schematic': ('#a8272f', '<path d="M7 7h18v18H7z"/><circle cx="16" cy="15" r="4" fill="#a8272f"/><path d="M16 20v3" stroke="#a8272f" stroke-width="2" fill="none"/><circle cx="16" cy="15" r="1.6"/>', W),
    # Layers
    'sky': ('#4f7fb3', '<path d="M9 22a5 5 0 0 1 1-10 7 7 0 0 1 13 2 4 4 0 0 1 0 8z"/>', W),
    'surface': ('#5f8f3f', '<path d="M4 24l8-12 5 7 3-4 8 9z"/>', W),
    'depths': ('#5a3f7a', '<path d="M8 8h16M10 13h12M12 18h8" stroke-width="2.4" stroke-linecap="round" fill="none"/><path d="M16 21l-4 4h8z"/>', W),
}


def svg(color, glyph, glyph_color):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
            f'<circle cx="16" cy="16" r="15" fill="{color}" stroke="#141414" stroke-width="1.5"/>'
            f'<g fill="{glyph_color}" stroke="{glyph_color}" stroke-width="0">{glyph}</g></svg>\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (color, glyph, gcolor) in ICONS.items():
        (OUT / f'{name}.svg').write_text(svg(color, glyph, gcolor), encoding='utf-8')
    print(f'{len(ICONS)} icons -> {OUT}')


if __name__ == '__main__':
    main()
