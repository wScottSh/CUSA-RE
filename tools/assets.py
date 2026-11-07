#!/usr/bin/env python3
"""Decode the asset table at ROM 0x80480 and check it against an ARES_PILOG DMA log.

Each 8-byte read into 0x800097F0 fetches one table entry; the next DMA must load
that entry (uncompressed: exact size; compressed: <= 0x8000 bytes into 0x800017F0).
See docs/architecture.md, section 4.

usage: assets.py ROM.z64 PILOG
"""
import struct, sys, collections
ROM = open(sys.argv[1], 'rb').read()
BASE = 0x80480
count = struct.unpack_from('>I', ROM, BASE)[0]

def entry(i):
    b0, b1, h2, w4 = struct.unpack_from('>BBHI', ROM, BASE + 4 + i * 8)
    return dict(idx=i, comp=b0 >> 7, kind=(b0 >> 4) & 7, method=b0 & 15,
                size=((b1 & 15) << 16) + h2,
                stored=(((b1 >> 4) << 8) | (w4 >> 24)) << 8,
                rom=BASE + (w4 & 0xFFFFFF))

E = [entry(i) for i in range(count)]
print(f"count=0x{count:X} ({count}) table_end=0x{BASE+4+count*8:X} first_rom=0x{min(e['rom'] for e in E):X}")
end = [e['rom'] + (e['stored'] if e['comp'] else e['size']) for e in E]
print(f"max data end=0x{max(end):X}")
by = collections.Counter((e['comp'], e['kind'], e['method']) for e in E)
for k, n in sorted(by.items()):
    sel = [e for e in E if (e['comp'], e['kind'], e['method']) == k]
    sz = [e['size'] for e in sel]
    print(f"comp={k[0]} kind={k[1]} method={k[2]}: n={n} size {min(sz)}..{max(sz)} rom 0x{min(e['rom'] for e in sel):X}..0x{max(e['rom'] for e in sel):X}")
dup = collections.Counter(e['rom'] for e in E)
print("entries sharing a rom offset:", sum(v for v in dup.values() if v > 1))

lines = [l.split() for l in open(sys.argv[2]) if l.startswith('L W')]
ok = bad = 0; badl = []
for j, l in enumerate(lines[:-1]):
    ln, dram, cart = int(l[2]), int(l[3], 16), int(l[4], 16)
    if ln == 8 and dram == 0x97f0:
        i = (cart - 0x10000000 - BASE - 4) // 8
        e = E[i]; n = lines[j + 1]
        nl, nd, nc = int(n[2]), int(n[3], 16), int(n[4], 16) - 0x10000000
        if nc == e['rom'] and (nl == e['size'] if not e['comp'] else nd == 0x17f0 and nl <= 0x8000):
            ok += 1
        else:
            bad += 1; badl.append((hex(i), e, n))
print(f"pilog check: {ok} match, {bad} mismatch")
for b in badl[:5]: print(b)
