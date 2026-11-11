# Progress log

Where the project stands, what was learned along the way, and what's next. Update it with each stage.

## Status (2026-11-11)

| | |
|---|---|
| Latest release | [v1.7.0](https://github.com/phatnguyen-v1/totk-progress/releases/tag/v1.7.0): spoiler-free mode (? markers), new-version notice (GitHub releases, off in Settings) |
| Release files | `TotKProgressMap.exe` 24.8 MB, SHA-256 `b4c623f3ee2e63586b6d2bc28c2e5b78a2d40d80445aa84ae18fd7350d99ab99`; `TotKProgressMap-linux-x86_64` 43.0 MB, SHA-256 `bd4b2bdf4088a70508fc68e0f47daa25a25047d560e44dd3295ec2c5b35d795e` |
| VirusTotal | v1.7.0 not scanned yet. v1.6.0 exe: 2 of 71 (Bkav Pro, SecureAge), every major engine clean |
| Release check | CI: both builds, Linux start-up smoke test. The CI exe started on the owner's PC: update check reached GitHub (1.7.0 = latest, no notice). Spoiler-free mode and the notice checked in the browser |
| Tested on | TotK Recomp v0.3.13 with game 1.2.1, English (USen), saves on `F:`; game 1.4.3 (owner 2026-11-10; a Reddit user with Recomp 0.3.7 + 1.4.3). Linux: CI smoke test only |

### Next up
1. Posted on r/decomps and the TotK Recomp Show and tell (2026-11-10); post a v1.6.0 update there.
2. Still untested: the Linux build on a real desktop / Steam Deck, the Browse… folder picker, a game folder
   outside `<drive>:\Games\TotK`, another Windows user.
3. The interface translations are drafts: corrections from native speakers welcome (`web/i18n/<code>.json`).
4. Later: Hyrule Compendium, armor upgrades; BotW (issue #2) is now its own app, [botw-progress](https://github.com/phatnguyen-v1/botw-progress) (v0.1.0, 2026-11-11); SignPath code signing
   once the project is more established.

## Done

### v1.0: progress map (2026-11-09)
- `savefile.py` reads `progress.sav`: (u32 hash, u32 value) table from 0x28 to `MetaData.SaveTypeHash`
  (0xa3db7114), then a u64 GUID array. Collectibles are done when their flag is set (shrines and Korok
  friends need `Clear`, lightroots `Open`); Sage's Wills and Addison's signs are done when their GUID is listed.
- Leaflet map with sky / surface / depths layers, filters (missing / done / all), search, Korok paths,
  live refresh every 4 s from the newest save slot.
- Map data and icons came from a third-party download (replaced by game files in v1.2, removed in v1.4).

### v1.0: quests (2026-11-09)
- 253 adventure-log quests from the game's `RSDB/Challenge` table + `Mals/<lang>` messages, read from the
  user's own TotK Recomp `romfs.bin` (`gamefiles.py`: zstd with the game's dictionaries, SARC, MSBT, BYML).
- Status from the save: enum `Step_<quest>` = murmur3 of the current step name (`NotReady` locked,
  `Ready` not started, `Complete` done).
- Prerequisites: `DependFlagName` flags and BoolExp programs from `GameData/GameDataList`, evaluated against
  the save (postfix: 0 GetBool, 10 BoolExp, 1/12 + 2 enum == / >, 3 AND, 4 OR, 5 NOT).
- Quest giver positions (160 exact, 92 approximate), "Queued" for later quests of the same NPC series
  (inferred from adventure-log order: same `Npc_*` giver, consecutive `SortIndex`).

### v1.1: Windows exe with guided setup (2026-11-09)
- `TotKProgressMap.exe` (PyInstaller, no console). Setup page finds TotK Recomp installs, folder picker,
  progress bar; data in `%LOCALAPPDATA%\TotKProgressMap`; single instance; settings (⚙) and Quit.
- Release v1.1.0 published by GitHub Actions on `v*` tags.

### v1.1.x follow-ups (2026-11-09)
- The page says "The app is not running…" instead of "Failed to fetch" when the background app was quit,
  and reconnects on its own (`67797a6`).

## v1.2.0 (released 2026-11-09): map built from the user's own game files (`cfebb32`)

Goal: no third-party download for TotK Recomp users; the repo ships no game-derived files.

| Stage | Status |
|---|---|
| 1. Decode the in-game map tiles and serve them as map layers | done: 720 WebP tiles, 14 MB |
| 2. Own icon set (SVG, `tools/make_icons.py`) | done: 23 icons |
| 3. Shrines, lightroots, caves, wells, chasms, places from the game's indexes | done |
| 4. Korok seeds, bosses, old maps, schematics, Sage's Wills, Addison's signs | done |
| 5. Check against third-party data and real saves | done: every save flag matches (see below) |
| 6. Setup builds everything locally | done (third-party Korok details and fallback map removed in v1.4) |
| 7. Tests, rebuild exe, docs, release | done: v1.2.0 released and checked |

Clean first run of the exe: 42 s, 14.2 MB data, same progress as before (7 Korok seeds, 4 shrines on
the test save). Existing installs rebuild in the background on the first start after updating, and
the old downloaded map images are deleted.

### Map tiles (`maptiles.py`)
- `UI/Map/MainField/<L>_<CC>-<RR>_<LOD>[_<variants>].bntx.zs`; `L`: `G` surface, `S` sky, `U` depths.
- `CC` column 00-11, `RR` row 00-09, 1000 x 1000 world units each (x -6000..6000, z -5000..5000).
- LOD `00` 3000 px (ASTC 12x12), `01` 840 px, `02` 300 px, `03` 135 px, `04` 27 px (ASTC 8x8), sRGB.
- Variants: one letter per map region, `T` revealed / `F` blueprint grid; `_A` / `_B` world-state
  variants (`A` used). Pick: most `T`, then `A`.
- BNTX, Tegra block-linear (block height `BRTI+0x34 & 7`), deswizzled in Python, ASTC decoded with
  `texture2ddecoder` (MIT), saved as WebP q80 with Pillow (PNG was 147 MB). Levels `02` (zoomed out)
  and `01` (zoomed in) as a Leaflet tile layer (`tileSize` 125 in the app's 1500 px space, rows offset
  by one tile because z starts at -5000). Outer depths tiles are genuinely black.

### Map data (`build_mapdata.py`)
Save flags are murmur3 of a name; per-object ones use the 64-bit placement instance ID:

| What | Source in the game files | Save flag |
|---|---|---|
| Shrines | `LocationArea` `Shrine` | `DungeonState.<DungeonNNN>` = Clear |
| Lightroots | MinusField `LocationArea` `CheckPoint` | `ArrivalPointState.<CheckPointNNN>` = Open |
| Caves / wells / chasms | `LocationArea` `CaveEntrance{Normal,Well,Special}` (one marker per entrance) | `IsVisitLocation.<name>` |
| Bubbul frogs | `CaveMarkerInfo` of a cave | `IsGetCaveMasterMedal.<cave>` |
| Places | `LocationArea` City, Stable, SkyArchipelago, DragonTears, Dungeon, SpotBig*, SpotMiddle* | `IsVisitLocation.<name>` |
| Device dispensers | `Banc/<Field>/RecycleBox` | `RecycleBoxData.<id>.IsVisit` |
| Korok seeds / friends | `Banc/MainField/HiddenKorok` (`HiddenKorok`, `CarryKorok`) | `IsAppearKorok.<id>` / `KorokCarryProgress.<id>` = Clear |
| Bosses | placed `Enemy_{Giant,Golem,Sandworm,Zonau,Mogurudo,Drake}*` whose flag exists | `IsDefeatBossEnemy.<id>` |
| Sage's Wills | chests with `Drop__DropActor: Obj_SageWill` | chest ID in the save's GUID array |
| Old maps | chests dropping `Obj_TreasureMap_NN`; `RSDB/PouchActorInfo` `TreasureMapContent` | `IsFindTreasureMap.<armor>` |
| Yiga schematics | chests dropping `Obj_AutoBuilderDraftAssassin_NN` | `ReadyMadeAutoBuilderDraft.<item>.IsOwned` |
| Schema stones | given by events: small table of which lab, position from `LocationArea` | same as above |
| Addison's signs | placed `Npc_CraftSignboard001` | sign ID in the GUID array |

Placement read from `Banc/{MainField,MinusField}/<A-J>-<1-8>_{Static,Dynamic}`, `Sky/`, `Cave/`,
`DeepHole/`, `LargeDungeon/`, `Castle/` (946 files, ~554k actors, ~7 s). Not from `Merged/`.

Compared with third-party data by save flag: identical for all categories; places 347 (the ones missing
are Bargainer Statues, Great Fairies, forge constructs etc. without an index), Bubbul frogs 146 of 147.

Bonus for later: `Drop__DropActor` gives the contents of all 1,341 field chests.

## v1.2.1 (released 2026-11-09): in-game icons (`build_icons.py`)

Markers now use the game's own icons, taken from the user's files at setup (0.5 s, 22 PNGs, 96 px, in
`assets/gameicons/`); existing installs build them on the next start. `web/icons/*.svg` stay as the
fallback (and for Addison's signs, which have no icon in the game).

| Icon | Source |
|---|---|
| Korok seeds / friends, caves, wells, chasms, locations | map UI glyphs `MapIconKorok^w`, `MapIconKorok_x2^w`, `MapIconCave{M,S,L}_72x72^w`, `MapIconBuildingVillage_58x58^w` |
| Shrines, lightroots, sky / surface / depths tabs | one-channel masks `MapIconDungeon_L_FrameIcon^s`, `MapIconArrivalPoint_L_FrameIcon^s`, `MapTabIcon_{Sky,Ground,Cave}^s`, coloured here (the game colours them in its layouts) |
| Bubbul frogs, Sage's Wills, old maps, schema stones, Yiga schematics | item icons `UI/Tex/Icon/{CaveMasterMedal,Obj_SageWill,Obj_TreasureMap_00,Obj_AutoBuilderDraft_00,Obj_AutoBuilderDraftAssassin_00}` |
| Bosses | compendium pictures `UI/Tex/PictureBook/Enemy_{Giant,Golem,Mogurudo,Zonau_BlockMaster}_Middle_Icon`, `Enemy_Sandworm_Icon`, `Enemy_Drake_Fire_Icon`, cut to a circle |

Map UI icons live in `UI/LayoutArchive/Common.Product.110.Nin_NX_NVN.blarc.zs` (SARC) ->
`timg/__Combined.bntx` (1,231 textures). Texture name at `BRTI+0x60` (pointer to u16 length + text).
Formats seen: `0x2d06` ASTC 4x4 sRGB (`^w` white glyphs), `0x1d01` BC4 (`^s` masks, value = coverage),
plus BC5/BC1/BC3/BC7; `maptiles.decode_texture` handles all of them.

## v1.7.0 (released 2026-11-11): spoiler-free mode, update notice

- Spoiler-free mode (`mystery` pref, legend checkbox): everything not done and not found is a "?" with no
  name, contents or route; one filter for all of them (`undiscovered` in the `off` list), the category
  filters only apply to found things, and a ? never matches the map search. The ? markers are canvas
  circles (`UnkMarker`): HTML markers for ~2,650 surface items cost ~28 ms per zoom step, canvas ~9 ms
  (default view ~6 ms).
- Update check (`server.Updates`): GitHub `releases/latest` at start and every 12 h, compared by version
  number; a notice with the release link, hidden per version (`updateSkip` pref); off with `update_check`
  in config.json (Settings -> Updates). Uses certifi: Python 3.12's view of the Windows certificate
  store failed on api.github.com ("unable to get issuer certificate") on the owner's PC.
- Local builds now run on Python 3.12 (same as CI); the exe is ~23.6 MB because numpy isn't installed
  there (never used; PyInstaller picked it up via Pillow on 3.13).

## v1.6.0 (released 2026-11-10): chests, more collectibles, all languages, Linux

- New layers from the placement data, each checked against the owner's save: armor chests (85) and all other
  treasure chests (1,177, off by default) named by `Drop__DropActor` (PouchContent names), opened = chest GUID
  in the save's GUID list; Dragon's Tears (12, `Complete_DragonTearsNN`, at the `FldObj_DragonTears_01` actor);
  Skyview Towers (15, `IsOpenCannon.TowerNN`); Great Fairies (4, `IsAppear_DressFairy_NN`); Lynels (34,
  locations only: their per-actor flags are Bool64bitKey with a Blood Moon reset type, 88 vs 80 for chests).
  Flag names found in the game's event flows (`DragonMemoryCommonFlow`, `LaunchPlayer`, `Npc_DressFairy_*`).
- Shrines at `DungeonState` `Open` / `Enter` (enum names are in GameDataList `RawValues`) get a "found, not
  completed" badge. Locations 366 -> 354 (the Dragon's Tears geoglyphs moved to their own layer).
- Layers added after a legend was saved start with their defaults (`known` pref), so nobody suddenly gets
  1,200 chest markers. `DATA_VERSION` 5, icon set 3 (game icons for all new layers).
- Languages: `gamelang.py` maps TotK Recomp's `totk.ini` `[language] lang` (or the Windows locale) to the
  game's 15 `Mals/<code>` languages; ⚙ can override it. Map data and quests are built in that language
  (`source.json` records it; a change rebuilds names and quests in about 10 s). The interface is translated
  to match (`web/i18n/<code>.json` merged over `USen.json`; regional variants inherit, e.g. `USfr` over `EUfr`).
- Linux build (`build_linux.sh`, single binary, map in the browser), built and smoke-tested in CI on
  ubuntu-22.04 (glibc 2.35+).

## v1.5.2 (released 2026-11-09): smoother zooming

- Map lag measured (zoom fps, all 1,770 markers on): tiles alone 100 fps; default 8 categories 92;
  everything 11; everything with small vector icons instead of the 96 px game icons also 11 (icon size
  isn't the cause); everything without per-marker effects 28. Removed the per-marker scale transition
  and the drop-shadow / grayscale filters (`.mk img`): everything now 30 fps, default 97. Done markers
  are faded (opacity .5) with the ✓ badge. Next step if needed: draw markers on one canvas.

## v1.5.1 (released 2026-11-09): phone fixes

- Phones start with their own, smaller legend (shrines, lightroots, caves, Bubbul frogs: `CATS[].phone`)
  and keep their settings under `totkp.phone.*` in their browser, so an older stored setting in that
  browser can't carry over.
- Small screens: the open side panel covered the ☰ button, so it couldn't be closed. Now a × in the
  panel header, a dimmed strip over the map that closes it on tap, and Esc.

## v1.5.0 (released 2026-11-09)

- Sky map: two tiles (5-6, 9-4) were brown squares. Their names have three suffix parts (`_T_A_A`), the
  old pattern only understood two, so the picker fell back to `_T_A`: a transparent overlay (islands
  only). `pick_variants` now reads any number of parts and prefers the most parts (complete tile), then
  the most T, then A. `maptiles.TILES_VERSION` (2) in `tiles/meta.json`: older tiles are deleted and
  redrawn on the next start (the resume-skip only applies within one version). Tile URLs carry
  `?v=<built>` so browsers and the app window don't keep the cached old tiles (served with a 1-day cache).
- Legend starts with 8 categories on (`CATS[].on`: shrines, lightroots, caves, Bubbul frogs, Sage's Wills,
  old maps, schema stones, Yiga schematics; ~455 markers instead of ~2,000).
- View settings (legend, filters, layer, tab, slot, quest options) are saved in `config.json` as `ui`
  (`GET/POST /api/prefs`, read synchronously at page start; localStorage only as fallback), so they survive
  restarts and port changes and are shared by the app window and the browser. Pending changes are sent
  on `pagehide`.
- *Open on your phone* (⚙): a second listener on the LAN address (`server.Lan`, same port, `lan_ip()` =
  the default-route interface), handler with `remote=True`: GET only for the page, assets, data,
  `/api/ping|setup|slots|progress|prefs` (setup without paths, slots without the save folder, prefs `{}`);
  every POST 403. Page: `REMOTE` hides ⚙, keeps its own view settings. QR as inline SVG from `segno`
  (BSD, pure Python). On/off saved as `lan` in `config.json`, restarted with the app. Phones: zoom buttons
  hidden under 760 px (pinch zoom), so the panel button is reachable.
- TotK Recomp ([valentderah/totk-pc-recomp](https://github.com/valentderah/totk-pc-recomp)) linked in the README (intro, requirements),
  the setup screen and the release notes.
- Floating phone button (bottom right, PC only) opens a popup with the same-network note, *Turn on* /
  *Turn off*, the QR code and the address; a green dot on the button while it's on. Settings shows the
  same (one `renderLan` for both).

- `send_file` no longer compares `resolve()`d paths: started from a packaged app (e.g. the Claude desktop
  app) AppData is redirected to `AppData\Local\Packages\<app>\LocalCache`, `resolve()` returned that
  path, and every asset answered 404. Now: absolute (not resolved) path inside the web or data folder and
  no `..` part. Traversal attempts (`..`, encoded, absolute paths) checked: 404.
- README screenshots (`docs/screenshots/*.webp`, taken with headless Edge from the running app) and
  release notes with an FAQ for v1.4.0.

## v1.4.0 (released 2026-11-09)

### Settings dialog

- ⚙ *Save* with the same, already set up folder now just closes (it used to rerun the whole setup).
  The dialog is titled *Settings* when opened from ⚙.
- An icon style option (game icons / the app's own) was tried and removed: extracting the game icons
  takes ~0.5 s of a ~45 s setup, so it saved nothing. The app's SVGs are only a fallback.

### Everything from the game files, no downloads

- Removed all third-party data: `fetch_assets.py` (fallback map download and the Korok puzzle details
  merge) is gone; setup needs TotK Recomp's game files (folders with only saves are refused with a
  message).
- Places with no LocationArea entry come from map labels: `LocationMarker` actors (`Dynamic.Location`)
  with an `IsVisitLocation.<name>` flag: 7 Bargainer Statues, 11 Forge Constructs, the Smithing
  Construct (`MARKER_PLACES`). 366 places now. 637 more labels have visit flags (lakes, hills, beaches,
  ...): candidates for an optional "landmarks" layer (field labels have y = 0, so sky/depths need care).
- Bubbul frogs: 146 from `CaveMarkerInfo` (the cave's map marker) plus the frog in the Ancient Zora
  Waterworks (`ZoraZonauTerminal`), which has no cave marker: taken from the `Enemy_CaveMaster_*` actor,
  whose `Dynamic.LocationName` names its place (147 frogs, one per place). 147 now.
- Checked with a 100% save (an edited one: it sets the Bubbul flag on every cave, well and chasm, so
  it can't identify frogs by itself): every category reads complete except 1 Sage's Will and 1 old map,
  which that save lacks; our counts (20, 31) match the game's totals and all entries are unique.
- Addison's signs have no icon in the game; they keep the app's drawn icon.
- Korok puzzle types from the game: the Korok actor's `Dynamic.HideType` (no HideType = under a lift
  rock; 10 = acorn, "in a hole" when an `Obj_KorokPotFixedVine` is within 30 m). Names are this
  project's own (`build_mapdata.HIDE_TYPES`).
- Routes from the game: flower trails = `Obj_Plant_Korok_A_01` grouped (< 60 m apart), ordered from
  `TrackingFlowerType` 1 by nearest neighbour, matched to the Korok by the last flower (type 2);
  races = nearest `FldObj_KorokStartingBlock_A_01` to the Korok; landing targets = start block to nearest
  `FldObj_KorokGoalBlock_A_02`; Korok friends = `KorokCarryPassenger_Pair` -> linked
  `KorokCarry_Destination`. Checked against the old merged data: all 800 types, all 107 seed routes and
  100 friend routes agree (flower order sometimes differs; ours walks the trail in order).
- `server.DATA_VERSION` (4) in `source.json`: older installs rebuild the map data on start (tiles kept).

### Map tiles fix

- Parts of the map went black at some zoom levels (e.g. 1.25). The two tile layers switched with their
  `minZoom`/`maxZoom`, which Leaflet checks against the *rounded* zoom, so with quarter-step zooms both
  could be off. Now the 300 px layer always stays and the 840 px layer is added on top from zoom 1.25
  (`DETAIL_ZOOM`, on `zoomend` and layer change). Checked: full coverage at every zoom -1.5..3, with the
  mouse wheel and when switching layers zoomed in, at 1850 x 1000.

## v1.3.0 (released 2026-11-09): app window, Link's position, app icon

- App icon: this project's own drawing (folded map, dotted trail, gold pin), `tools/make_app_icon.py` ->
  `app.ico` (exe, `--icon`; pywebview uses the exe's icon for the window and taskbar) and
  `web/app-icon.png` (browser tab).

- The exe shows the map in its own window (pywebview + Edge WebView2, `server.run_window`), opened at
  `/?app=1`; closing the window stops the app. The HTTP server runs on a background thread.
- Second launch: `POST /api/focus` brings the running window to the front (falls back to opening the
  browser). `/api/ping` reports `mode` (`window` / `browser`).
- In the window the page hides *Quit app* and shows *Open in browser* (`POST /api/open-browser`).
- Fallback: no pywebview or no WebView2 runtime -> the browser as before, with *Quit app*.
  `--browser` forces it, `--no-browser` runs the server only. WebView2 data (localStorage) in
  `<data>/webview`.
- Link's position at the last save: Vector3 `PlayerStatus.SavePos` (table value = offset of 3 floats),
  `savefile.player_position`, returned as `player` by `/api/progress`. Shown as the game's player arrow
  (`Nt_MapPlayerIconNew_00^s`, yellow) on Link's layer, plus a **Link** button that flies there. The save
  doesn't seem to store which way Link faces, so the arrow always points up.
- Icons: `build_icons.VERSION` (now 2) in `meta.json`; the app rebuilds icons when it changes. Glyphs
  are cropped to their visible part and scaled up as well as down (some are ~25 px in their texture).
  Icon URLs carry `?v=<built>` so browsers don't show stale cached icons after a rebuild.

## Ideas for later
- "What changed since last save" feed, You-are-here (`PlayerStatus.SavePos`), nearest missing items.
- Hyrule Compendium, armor upgrades (treasure chests with contents: done in v1.6.0).
- Emulator support: detect Ryujinx / yuzu-fork save folders, read quests from a dumped RomFS.
- Phone as second screen (`--host 0.0.0.0`).
