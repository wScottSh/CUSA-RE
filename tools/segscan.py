#!/usr/bin/env python3
"""List every ROM byte range found verbatim in RDRAM of ares save states.

ares stores RDRAM as little-endian 32-bit words. The state offset is found by
locating the boot segment, which is always resident at 0x80100000.

usage: segscan.py ROM.z64 STATE.bst [STATE.bst ...] [--min 0x400] [--rom-range 0x1000:0x100000]
"""
import argparse
import struct

RDRAM_SIZE = 0x800000
BOOT_ROM, BOOT_PHYS = 0x1000, 0x100000
WINDOW = 32


def swap32(b: bytes) -> bytes:
    n = len(b) // 4 * 4
    return struct.pack(f">{n // 4}I", *struct.unpack(f"<{n // 4}I", b[:n]))


def extract_rdram(rom: bytes, state: bytes) -> bytes:
    probe = swap32(rom[BOOT_ROM + 0x100:BOOT_ROM + 0x140])
    hit = state.find(probe)
    if hit < 0:
        raise SystemExit("boot segment not found in state")
    base = hit - (BOOT_PHYS + 0x100)
    return swap32(state[base:base + RDRAM_SIZE])


def scan(rom: bytes, ram: bytes, lo: int, hi: int, min_len: int):
    index = {}
    for r in range(lo, hi - WINDOW, 16):
        index.setdefault(rom[r:r + WINDOW], r)
    runs, p = [], 0
    while p < len(ram) - WINDOW:
        r = index.get(ram[p:p + WINDOW])
        if r is None or ram[p:p + WINDOW].count(0) > WINDOW // 2:
            p += 4
            continue
        s_ram, s_rom = p, r
        while s_ram > 0 and s_rom > lo and ram[s_ram - 4:s_ram] == rom[s_rom - 4:s_rom]:
            s_ram, s_rom = s_ram - 4, s_rom - 4
        e = p
        while e < len(ram) and r + (e - p) < hi and ram[e:e + 4] == rom[r + (e - p):r + (e - p) + 4]:
            e += 4
        if e - s_ram >= min_len:
            runs.append((s_rom, s_rom + (e - s_ram), 0x80000000 + s_ram))
        p = max(e, p + 4)
    return runs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("states", nargs="+")
    ap.add_argument("--min", type=lambda s: int(s, 0), default=0x400)
    ap.add_argument("--rom-range", default="0x1000:0x750000")
    a = ap.parse_args()
    lo, hi = (int(x, 0) for x in a.rom_range.split(":"))
    rom = open(a.rom, "rb").read()
    for path in a.states:
        ram = extract_rdram(rom, open(path, "rb").read())
        print(f"# {path}")
        print("rom_start\trom_end\tvram\tsize")
        for s, e, v in sorted(scan(rom, ram, lo, hi, a.min), key=lambda t: t[2]):
            print(f"{s:#08x}\t{e:#08x}\t{v:#010x}\t{e - s:#x}")


if __name__ == "__main__":
    main()
