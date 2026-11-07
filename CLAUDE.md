# Cruis'n USA (N64) reverse engineering

ROM: `ROM/Cruis'n USA.z64` (big-endian, 8 MiB, SHA-1 54a875ee0b482036fa401a6bc2b242699f0259f7, ID NCUE, entry 0x80100000).

## Tooling
- REA MCP server (`.mcp.json`, project scope) → `~/repos/rea` built with Node 24.22.1 (`~/tools/node-v24.22.1-linux-x64`), Ghidra 12.1.4 (`~/tools/ghidra_12.1.4_PUBLIC`).
- Skill: `.claude/skills/reverse-engineer-anything` (symlink to rea build output).
- CLI: `PATH=~/tools/node-v24.22.1-linux-x64/bin:$PATH GHIDRA_INSTALL_DIR=~/tools/ghidra_12.1.4_PUBLIC REA_GHIDRA_LANGUAGE_ID=MIPS:BE:64:64-32addr node ~/repos/rea/scripts/rea.mjs <cmd> ...`

## Target for REA: `build/cusa_boot.elf`, not the .z64
REA has no N64/raw-MIPS lane. `tools/rom2elf.py` wraps the boot segment in an ELF32 BE MIPS ET_EXEC (e_flags=0) that REA's legacy MIPS lane admits:
- ROM 0x1000..0x3D860 → 0x80100000..0x8013C860 (code+data); BSS 0x8013C860, size 0x28FE0 (from entry stub's clear loop).
- Rebuild: `python3 tools/rom2elf.py "ROM/Cruis'n USA.z64" build/cusa_boot.elf`
- `REA_GHIDRA_LANGUAGE_ID=MIPS:BE:64:64-32addr` (VR4300; decodes 64-bit ops in libultra). Applies to every Ghidra import in that REA server.

## Caveats
- Address args resolve only at function starts / symbols (e.g. `0x8011fbc0`, `FUN_8011f990`, `entry`); other hex falls back to file-offset lookup and errors.
- Decompiler shows sign-extended pointers (`0xffffffff8013c960`) — artifact of the 64-32addr language.
- Only the boot segment is mapped. Code DMA'd later from ROM (overlays) is not yet located/added.
- REA sessions are ephemeral: names/comments are discarded on close.
