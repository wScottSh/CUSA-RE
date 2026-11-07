#!/usr/bin/env python3
"""Wrap the Cruis'n USA boot segment in an ELF32 big-endian MIPS executable.

REA has no N64/raw-MIPS lane; its "recordless legacy MIPS" ELF lane admits
ET_EXEC with e_flags=0 (MIPS-I, no ABI) and no ABI-flags record.

Boot segment facts (from the ROM entry stub at 0x80100000):
  ROM 0x1000 is copied to the header entry point 0x80100000.
  The stub zeroes BSS at 0x8013C860, length 0x28FE0, so code+data end there.
"""
import struct
import sys

ROM_OFFSET = 0x1000
VADDR = 0x80100000
BSS_START = 0x8013C860
BSS_SIZE = 0x28FE0


def main(rom_path: str, out_path: str) -> None:
    rom = open(rom_path, "rb").read()
    if rom[:4] != b"\x80\x37\x12\x40":
        sys.exit("not a big-endian .z64 ROM")
    entry = struct.unpack(">I", rom[8:12])[0]
    if entry != VADDR:
        sys.exit(f"unexpected entry point {entry:#x}")

    filesz = BSS_START - VADDR
    memsz = filesz + BSS_SIZE
    payload = rom[ROM_OFFSET:ROM_OFFSET + filesz]

    ehsize, phentsize = 52, 32
    data_off = 0x1000
    ehdr = struct.pack(
        ">16sHHIIIIIHHHHHH",
        b"\x7fELF\x01\x02\x01" + b"\x00" * 9,  # ELF32, BE, v1
        2,          # ET_EXEC
        8,          # EM_MIPS
        1,          # EV_CURRENT
        entry,
        ehsize,     # e_phoff
        0,          # e_shoff (no section table)
        0,          # e_flags: EF_MIPS_ARCH_1, no ABI
        ehsize, phentsize, 1,
        0, 0, 0,
    )
    phdr = struct.pack(
        ">IIIIIIII",
        1,          # PT_LOAD
        data_off, VADDR, VADDR, filesz, memsz,
        7,          # RWX
        0x1000,
    )
    header = ehdr + phdr
    with open(out_path, "wb") as f:
        f.write(header + b"\x00" * (data_off - len(header)) + payload)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} ROM.z64 OUT.elf")
    main(sys.argv[1], sys.argv[2])
