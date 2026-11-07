#!/usr/bin/env python3
"""Build one ELF and one REA seed file per address-space view from the ROM.

REA has no N64 lane. Its legacy MIPS ELF lane admits ELF32 BE ET_EXEC with
e_flags = 0 and no ABI-flags record, so each view is written in that shape:
two PT_LOADs per segment (text R-X, data RW- with BSS as memsz), bytes from the ROM.

usage: build.py            writes build/<view>.elf and build/<view>.seeds.tsv
"""
import hashlib
import struct
import sys

from layout import ROM_PATH, ROOT, Layout, Segment, Symbol, load_layout, load_symbols

OUT = ROOT / "build"
EHDR, PHDR, ALIGN = 52, 32, 0x10
SEED_KIND = {"func": "function", "label": "label", "data": "label"}


PF_X, PF_W, PF_R = 1, 2, 4


def loads(s: Segment) -> list[tuple[int, int, int, int, int]]:
    """(rom_start, rom_end, vram, memsz, flags): text is R-X, data and BSS are RW-."""
    text = (s.rom_start, s.text_rom_end, s.vram, s.text_end - s.vram, PF_R | PF_X)
    data = (s.text_rom_end, s.rom_end, s.text_end, s.bss_end - s.text_end, PF_R | PF_W)
    return [text, data] if data[3] else [text]


def write_elf(entry: int, segments: tuple[Segment, ...], rom: bytes) -> bytes:
    parts = [p for s in segments for p in loads(s)]
    data_off = (EHDR + PHDR * len(parts) + ALIGN - 1) & ~(ALIGN - 1)
    phdrs, body = b"", b""
    for start, end, vram, memsz, flags in parts:
        off = data_off + len(body)
        phdrs += struct.pack(">8I", 1, off, vram, vram, end - start, memsz, flags, ALIGN)
        body += rom[start:end]
        body += b"\0" * (-len(body) % ALIGN)
    ehdr = struct.pack(
        ">16sHHIIIIIHHHHHH",
        b"\x7fELF\x01\x02\x01" + b"\0" * 9,
        2, 8, 1, entry, EHDR, 0, 0, EHDR, PHDR, len(parts), 0, 0, 0,
    )
    head = ehdr + phdrs
    return head + b"\0" * (data_off - len(head)) + body


def owner(sym: Symbol, layout: Layout) -> Segment:
    if sym.rom is not None:
        seg = layout.segment_at_rom(sym.rom)
        if seg.rom_of(sym.vram) != sym.rom:
            raise ValueError(f"{sym.name}: rom {sym.rom:#x} does not map to {sym.vram:#x} in {seg.name}")
        return seg
    hits = [s for s in layout.segments if s.rom_of(sym.vram) is not None]
    if len(hits) != 1 or hits[0].overlay:
        raise ValueError(f"{sym.name}: {sym.vram:#x} is ambiguous or in an overlay; add rom:")
    return hits[0]


def seeds(view: tuple[Segment, ...], symbols: list[tuple[Symbol, Segment]]) -> str:
    rows = [f"0x{s.vram:08x}\t{SEED_KIND[s.kind]}\t{s.name}" for s, seg in symbols if seg in view]
    return "".join(r + "\n" for r in sorted(rows))


def main() -> None:
    layout = load_layout()
    rom = ROM_PATH.read_bytes()
    if hashlib.sha1(rom).hexdigest() != layout.rom_sha1:
        sys.exit(f"{ROM_PATH} is not the expected ROM (sha1 {layout.rom_sha1})")
    symbols = [(s, owner(s, layout)) for s in load_symbols()]
    OUT.mkdir(exist_ok=True)
    for name, view in layout.views().items():
        (OUT / f"{name}.elf").write_bytes(write_elf(layout.entry, view, rom))
        (OUT / f"{name}.seeds.tsv").write_text(seeds(view, symbols))
        print(f"build/{name}.elf: {' + '.join(s.name for s in view)}")


if __name__ == "__main__":
    main()
