# Cruis'n USA reverse engineering

Tools and notes for reading the code of Cruis'n USA (N64, USA release) in Ghidra through [REA](https://github.com/morluto/rea).
The repository contains no game data. You supply your own ROM.

## What is here

- `segments.toml` describes where every piece of code sits in the ROM and in RAM. The values come from the game's own overlay table and are confirmed against emulator memory.
- `tools/build.py` turns the ROM into three ELF files, one per overlay (boot, frontend, race), that Ghidra and REA can open.
- `symbols.lib.txt` names 138 libultra functions found by signature matching (`tools/libsigs.py`).
- `tools/check.py` and `tools/verify_runtime.py` check the layout statically and in a running emulator.
- `docs/architecture.md` explains boot, threads, overlay loading and the ROM data layout.
- `PLAN.md` holds the goals, and `decisions.tsv` records why each step was taken.

## Code layout

| Segment | ROM | RAM | Loaded |
|---|---|---|---|
| main | 0x1000-0x3D860 | 0x80100000 | at boot, always resident |
| low | 0x7F110-0x80480 | 0x80000480 | at boot, reloaded later |
| ovl_boot | 0x3D860-0x3E6F0 | 0x80025C80 | before the first logo |
| ovl_frontend | 0x5EA10-0x7F110 | 0x80025C80 | intro, attract mode, menus |
| ovl_race | 0x3E6F0-0x5EA10 | 0x80025C80 | during a race |

## Use

Requirements: Python 3.11 or later, Ghidra 12.1, REA, and Node.js 24 for REA. `verify_runtime.py` also needs the `n64-run` tool from an ares fork.

1. Put the ROM at `ROM/Cruis'n USA.z64` (SHA-1 `54a875ee0b482036fa401a6bc2b242699f0259f7`).
2. Build the ELF views:

   ```bash
   python3 tools/build.py
   ```

3. Check the result:

   ```bash
   python3 tools/check.py
   ```

4. Decompile a function with names applied:

   ```bash
   tools/rea race decompile entry --format json
   ```

`tools/rea` and `.mcp.json` assume the tool paths in `CLAUDE.md`. Change them for your machine.
