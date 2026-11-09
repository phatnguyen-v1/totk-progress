# Progress log

Where the project stands, what was learned along the way, and what's next. Update it with each stage.

## Done

### v1.0: progress map (2026-11-09)
- `savefile.py` reads `progress.sav`: (u32 hash, u32 value) table from 0x28 to `MetaData.SaveTypeHash`
  (0xa3db7114), then a u64 GUID array. Collectibles are done when their flag is set (shrines and Korok
  friends need `Clear`, lightroots `Open`); Sage's Wills and Addison's signs are done when their GUID is listed.
- Leaflet map with sky / surface / depths layers, filters (missing / done / all), search, Korok paths,
  live refresh every 4 s from the newest save slot.
- Map data and icons downloaded from lud99/totk-unexplored by `fetch_assets.py`.

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

## v1.2 (unreleased): map built from the user's own game files (2026-11-09)

Goal: no third-party download for TotK Recomp users; the repo ships no game-derived files.

| Stage | Status |
|---|---|
| 1. Decode the in-game map tiles and serve them as map layers | done: 720 WebP tiles, 14 MB |
| 2. Own icon set (SVG, `tools/make_icons.py`) | done: 23 icons |
| 3. Shrines, lightroots, caves, wells, chasms, places from the game's indexes | done |
| 4. Korok seeds, bosses, old maps, schematics, Sage's Wills, Addison's signs | done |
| 5. Check against lud99's data and real saves | done: every save flag matches (see below) |
| 6. Setup builds everything locally; lud99 only for Korok puzzle details / fallback | done |
| 7. Tests, rebuild exe, docs | done; release pending |

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

Compared with lud99's data by save flag: identical for all categories; places 333 of 360 (the rest are
Bargainer Statues, Great Fairies, forge constructs etc. without an index), Bubbul frogs 146 of 147.

Taken from lud99's `map_data.json` when online (`merge_reference`, matched by flag): Korok puzzle
types and routes (all 900), and those ~27 extra places / 1 Bubbul frog. Offline, Koroks show as
"Flying Korok" / "Hidden Korok" without routes.

Bonus for later: `Drop__DropActor` gives the contents of all 1,341 field chests.

## Ideas for later
- "What changed since last save" feed, You-are-here (`PlayerStatus.SavePos`), nearest missing items.
- Treasure chests with contents (chest `Drop__DropActor` + opened flags), Hyrule Compendium, armor upgrades.
- Korok puzzle types/routes from the game itself (puzzle actors near each Korok) to drop the last lud99 use.
- Emulator support: detect Ryujinx / yuzu-fork save folders, read quests from a dumped RomFS.
- Phone as second screen (`--host 0.0.0.0`).
