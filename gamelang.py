"""The game's text languages (Mals/<code>.Product.*.sarc.zs) and which one TotK Recomp is set to.

TotK Recomp's totk.ini has `[language] lang = ...`: a Windows locale such as de-DE, or a Switch code (en-US,
ja, zh-Hant, ...); empty means the Windows locale. The map data and quests are built in that language unless
the user picks another one in Settings.
"""
import re
from pathlib import Path

DEFAULT = 'USen'
# game code -> name shown in Settings (in that language)
LANGUAGES = {
    'USen': 'English (US)', 'EUen': 'English (UK)', 'USfr': 'Français (Canada)', 'EUfr': 'Français',
    'EUde': 'Deutsch', 'USes': 'Español (Latinoamérica)', 'EUes': 'Español (España)', 'EUit': 'Italiano',
    'EUnl': 'Nederlands', 'USpt': 'Português (Brasil)', 'EUru': 'Русский', 'JPja': '日本語', 'KRko': '한국어',
    'CNzh': '简体中文', 'TWzh': '繁體中文',
}
# game code -> browser locale, for the page's own words, dates and numbers
LOCALES = {
    'USen': 'en-US', 'EUen': 'en-GB', 'USfr': 'fr-CA', 'EUfr': 'fr-FR', 'EUde': 'de-DE', 'USes': 'es-419',
    'EUes': 'es-ES', 'EUit': 'it-IT', 'EUnl': 'nl-NL', 'USpt': 'pt-BR', 'EUru': 'ru-RU', 'JPja': 'ja-JP',
    'KRko': 'ko-KR', 'CNzh': 'zh-CN', 'TWzh': 'zh-TW',
}
# Latin American Spanish locales (es-419 is the Switch's own code)
_LATAM_ES = {'419', 'MX', 'US', 'AR', 'CL', 'CO', 'PE', 'VE', 'EC', 'GT', 'CU', 'BO', 'DO', 'HN', 'PY', 'SV', 'NI',
             'CR', 'PR', 'PA', 'UY'}


def from_locale(tag):
    """'de-DE' / 'en-US' / 'ja' / 'zh-Hant' / 'es-419' / 'fr_CA' -> game code, or None if the game doesn't have it."""
    if not tag:
        return None
    parts = re.split(r'[-_]', tag.strip())
    lang = parts[0].lower()
    rest = [p for p in parts[1:] if p]
    region = next((p.upper() for p in rest if len(p) == 2 or (len(p) == 3 and p.isdigit())), '')   # US, 419
    script = next((p.title() for p in rest if len(p) == 4), '')                                 # Hant
    if lang == 'en':
        return 'USen' if region in ('', 'US', 'CA') else 'EUen'
    if lang == 'fr':
        return 'USfr' if region == 'CA' else 'EUfr'
    if lang == 'es':
        return 'USes' if region in _LATAM_ES else 'EUes'
    if lang == 'pt':
        return 'USpt'   # the only Portuguese the game has
    if lang == 'zh':
        return 'TWzh' if script == 'Hant' or region in ('TW', 'HK', 'MO') else 'CNzh'
    return {'de': 'EUde', 'it': 'EUit', 'nl': 'EUnl', 'ru': 'EUru', 'ja': 'JPja', 'ko': 'KRko'}.get(lang)


def windows_locale():
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(85)
        if ctypes.windll.kernel32.GetUserDefaultLocaleName(buf, 85):
            return buf.value
    except Exception:
        pass
    return None


def recomp_setting(install_dir):
    """The `lang` value in TotK Recomp's totk.ini ('' when not set), or None without a totk.ini."""
    ini = Path(install_dir) / 'totk.ini'
    try:
        text = ini.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    section = None
    for line in text.splitlines():
        line = line.split('#', 1)[0].split(';', 1)[0].strip()
        m = re.match(r'\[(.+)\]$', line)
        if m:
            section = m.group(1).strip().lower()
        elif section == 'language' and '=' in line:
            key, value = (s.strip() for s in line.split('=', 1))
            if key.lower() == 'lang':
                return value.strip('"\'')
    return ''


def game_language(install_dir):
    """The language TotK Recomp shows the game in: its totk.ini setting, else the Windows locale."""
    setting = recomp_setting(install_dir) if install_dir else None
    return from_locale(setting) or from_locale(windows_locale()) or DEFAULT


def available(romfs):
    """Language codes the game files have text for."""
    return sorted({p.split('/')[1].split('.')[0] for p in romfs.find('Mals/')} & set(LANGUAGES))
