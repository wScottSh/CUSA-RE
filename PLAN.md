# Cruis'n USA reverse-engineering plan

## Goal

Make the game's code fully readable in REA/Ghidra from one command, with names and docs that rest on runtime evidence.
A matching decompilation is a later program. This plan builds the base it would stand on.

## Definition of done (this run)

Each item is a check a script or command can run.

1. **Segment table is complete.** `tools/check.py` finds no code-like ROM block outside a declared code segment.
2. **Segment table is true at runtime.** For every code segment, its ROM bytes match an emulator RDRAM snapshot at its VRAM (`tools/verify_runtime.py`).
3. **Build is reproducible.** `tools/build.py` regenerates every ELF and seed file from the ROM. Two runs give identical bytes.
4. **Map is closed.** In each ELF view, at least 95% of `jal` targets land in mapped code.
5. **libultra is named.** Library functions are named in `symbols.txt`, and REA output shows the names.
6. **Architecture is documented.** `docs/architecture.md` covers boot, threads, segment loading and ROM layout. Each claim cites an address.

## Status

All six done-items pass. `tools/check.py --rea` covers 1, 3, 4 and 5. `tools/verify_runtime.py` covers 2. `docs/architecture.md` covers 6.

- Code layout comes from the game's overlay table at 0x801321D0 and matches emulator RAM (100% text match per segment).
- 138 libultra names come from signatures, and about 40 hand names come from reading code.
- The asset table at ROM 0x80480 (12518 entries) is decoded and checked against two DMA logs.

## Phases

1. **Runtime harness.** Build ares `n64-run` out of tree. Boot the ROM headless, save states at checkpoints, extract RDRAM.
2. **Segment discovery.** Match RDRAM snapshots against ROM to recover every (ROM range, VRAM) pair. Trace the loader routine that does it.
3. **Segment table.** One data file, `segments.toml`, owns the layout. Every tool reads it.
4. **ELF views.** `build.py` emits one ELF per address-space view: resident segments plus one overlay, so overlapping overlays never share a view.
5. **Symbols.** `symbols.txt` in splat format is the persistent name store. `build.py` converts it to REA seed TSVs. Identify libultra by signature matching.
6. **Subsystem docs.** Boot, thread layout, main loop, loader, ROM asset layout.
7. **Checks.** `check.py` runs predicates 1, 3, 4, 5. `verify_runtime.py` runs predicate 2.

## Later programs (not this run)

- Asset formats: decompression, track data, models, textures, audio.
- splat config and a matching decompilation (compiler identification first).
- Gameplay systems: car physics, AI, track streaming.
