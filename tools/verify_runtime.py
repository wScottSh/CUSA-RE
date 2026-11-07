#!/usr/bin/env python3
"""Boot the ROM in ares n64-run to a race and check every segment's text against RDRAM.

Each segment's text must match RAM word for word (at least 99%) in one of the
checkpoints that tools/to_race.script saves. Exit 1 on failure.

usage: verify_runtime.py [--n64-run PATH]
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from layout import ROM_PATH, ROOT, load_layout
from segscan import extract_rdram

MATCH = 0.99
STATES = ("boot", "frontend", "race")


def text_match(seg, rom: bytes, ram: bytes) -> float:
    phys = seg.vram & 0x1FFFFFFF
    n = (seg.text_end - seg.vram) // 4
    a = rom[seg.rom_start:seg.text_rom_end]
    b = ram[phys:phys + n * 4]
    return sum(a[i:i + 4] == b[i:i + 4] for i in range(0, n * 4, 4)) / n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n64-run", default=str(Path.home() / "tools/ares-n64run-build/rundir/bin/n64-run"))
    a = ap.parse_args()
    work = ROOT / "build/runtime"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    subprocess.run([a.n64_run, "--script", str(ROOT / "tools/to_race.script"), "--wall-seconds", "600", str(ROM_PATH)],
                   cwd=work, check=True, capture_output=True)
    rom = ROM_PATH.read_bytes()
    rams = {s: extract_rdram(rom, (work / f"{s}.bst").read_bytes()) for s in STATES}
    failed = False
    for seg in load_layout().segments:
        scores = {s: text_match(seg, rom, ram) for s, ram in rams.items()}
        best = max(scores, key=scores.get)
        ok = scores[best] >= MATCH
        failed |= not ok
        detail = " ".join(f"{s}={v:.1%}" for s, v in scores.items())
        print(f"{'ok  ' if ok else 'FAIL'} {seg.name}: {detail}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
