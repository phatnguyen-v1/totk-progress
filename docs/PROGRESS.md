# Progress log

Where the project stands, what was learned along the way, and what's next. Update it with each stage.

## Status (2026-11-09)

| | |
|---|---|
| Latest release | [v1.4.0](https://github.com/phatnguyen-v1/totk-progress/releases/tag/v1.4.0): everything from the game files (no downloads), 147 Bubbul frogs, 366 places, map tiles fix |
| Release exe | 24.4 MB, SHA-256 `4e0924e3ca87fc69cbc525e034bc9e79c7b9759389f33ed85cd45090cd7bce63` |
| Release check | downloaded exe, clean data folder: app window, saves-only folder refused, setup 42 s, no errors, no downloads; 147 Bubbul frogs, 366 places, 107 + 100 Korok routes, 23 game icons; progress, 253 quests and Link's position read; Quit exits |
| Tested on | one PC: TotK Recomp v0.3.13, game 1.2.1, English (USen), saves on `F:` |

### Next up
1. Before posting on Reddit (r/decomps first):
   - VirusTotal scan of the release exe, link + SHA-256 in the release notes
   - screenshots / GIF in the README (map, Quests tab)
   - test the Browse… folder picker, a game folder outside `<drive>:\Games\TotK`, another Windows user,
     game 1.4.3 saves, non-English game files
   - release text with an FAQ (SmartScreen warning, read-only, what "Queued" means)

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
- Treasure chests with contents (chest `Drop__DropActor` + opened flags), Hyrule Compendium, armor upgrades.
- Emulator support: detect Ryujinx / yuzu-fork save folders, read quests from a dumped RomFS.
- Phone as second screen (`--host 0.0.0.0`).
