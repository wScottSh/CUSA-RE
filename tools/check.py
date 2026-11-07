#!/usr/bin/env python3
"""Static checks for the layout, the build and the names. Exit 1 on any failure.

usage: check.py [--rea]     --rea also decompiles entry through REA (about 15 s)
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from layout import ROM_PATH, ROOT, load_layout, load_symbols

CODE_BLOCK = 0x1000
CODE_MARKERS = 4
JAL_CLOSURE = 0.95
HOME = Path.home()


def word(rom: bytes, off: int) -> int:
    return int.from_bytes(rom[off:off + 4], "big")


def check_table(layout, rom) -> list[str]:
    main = next(s for s in layout.segments if s.name == "main")
    base = main.rom_of(layout.overlay_table)
    errors = []
    for s in layout.segments:
        if s.table_index is None:
            continue
        got = [word(rom, base + (s.table_index * 6 + i) * 4) for i in range(6)]
        want = [s.rom_start, s.rom_end, s.vram, s.bss_end, s.bss_start, s.bss_end]
        if got != want:
            errors.append(f"{s.name}: overlay table says {[hex(x) for x in got]}")
    return errors


def gaps(layout, rom_size: int) -> list[tuple[int, int]]:
    out, pos = [], 0x1000
    for seg in sorted(layout.segments, key=lambda s: s.rom_start):
        if seg.rom_start > pos:
            out.append((pos, seg.rom_start))
        pos = max(pos, seg.rom_end)
    return out + [(pos, rom_size)]


def check_coverage(layout, rom) -> list[str]:
    errors = []
    for start, end in gaps(layout, len(rom)):
        for blk in range(start, end, CODE_BLOCK):
            words = [word(rom, o) for o in range(blk, min(blk + CODE_BLOCK, end), 4)]
            markers = words.count(0x03E00008) + sum(1 for w in words if w >> 16 == 0x27BD and w & 0x8000)
            if markers >= CODE_MARKERS:
                errors.append(f"ROM {blk:#x}: {markers} code markers outside any segment")
    return errors


def check_text_end(layout, rom) -> list[str]:
    errors = []
    for s in layout.segments:
        last = max(o for o in range(s.rom_start, s.text_rom_end, 4) if word(rom, o))
        if 0x03E00008 not in (word(rom, last), word(rom, last - 4)):
            errors.append(f"{s.name}: text_end {s.text_end:#x} does not follow a jr ra and padding")
    return errors


def check_jal_closure(layout, rom) -> list[str]:
    errors = []
    for name, view in layout.views().items():
        total = hit = 0
        for seg in view:
            for off in range(seg.rom_start, seg.text_rom_end, 4):
                w = word(rom, off)
                if w >> 26 == 3:
                    total += 1
                    target = 0x80000000 | (w & 0x03FFFFFF) << 2
                    hit += any(s.rom_of(target) is not None for s in view)
        share = hit / total
        print(f"  view {name}: {hit}/{total} jal targets mapped ({share:.1%})")
        if share < JAL_CLOSURE:
            errors.append(f"view {name}: only {share:.1%} of jal targets mapped")
    return errors


def check_reproducible() -> list[str]:
    def digest():
        subprocess.run([sys.executable, str(ROOT / "tools/build.py")], check=True, capture_output=True)
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "build").glob("*.elf"))}
    first, second = digest(), digest()
    return [] if first == second and first else ["build.py output differs between runs"]


def check_rea() -> list[str]:
    env = dict(
        os.environ,
        PATH=f"{HOME}/tools/node-v24.22.1-linux-x64/bin:{os.environ['PATH']}",
        GHIDRA_INSTALL_DIR=f"{HOME}/tools/ghidra_12.1.4_PUBLIC",
        REA_GHIDRA_LANGUAGE_ID="MIPS:BE:64:64-32addr",
        REA_GHIDRA_SEED_FILE=str(ROOT / "build/race.seeds.tsv"),
    )
    out = subprocess.run(
        ["node", f"{HOME}/repos/rea/scripts/rea.mjs", "decompile", str(ROOT / "build/race.elf"), "entry",
         "--provider", "ghidra", "--format", "json"],
        env=env, capture_output=True, text=True,
    ).stdout
    return [] if "osCreateThread(" in out else ["REA decompile of entry does not show seeded names"]


def main() -> None:
    layout = load_layout()
    rom = ROM_PATH.read_bytes()
    load_symbols()
    checks = {
        "overlay table matches segments.toml": lambda: check_table(layout, rom),
        "no code outside segments": lambda: check_coverage(layout, rom),
        "text_end follows the last function": lambda: check_text_end(layout, rom),
        "jal targets land in mapped code": lambda: check_jal_closure(layout, rom),
        "build is reproducible": check_reproducible,
    }
    if "--rea" in sys.argv:
        checks["REA shows seeded names"] = check_rea
    failed = False
    for label, run in checks.items():
        errors = run()
        print(f"{'FAIL' if errors else 'ok  '} {label}")
        for e in errors:
            print(f"     {e}")
        failed |= bool(errors)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
