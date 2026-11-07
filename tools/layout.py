"""Parse segments.toml and symbols.txt into typed records. Every tool goes through here."""
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROM_PATH = ROOT / "ROM" / "Cruis'n USA.z64"


@dataclass(frozen=True)
class Segment:
    name: str
    rom_start: int
    rom_end: int
    vram: int
    bss_start: int
    bss_end: int
    overlay: bool
    table_index: int | None

    @property
    def size(self) -> int:
        return self.rom_end - self.rom_start

    def holds_rom(self, rom: int) -> bool:
        return self.rom_start <= rom < self.rom_end

    def rom_of(self, vram: int) -> int | None:
        off = vram - self.vram
        return self.rom_start + off if 0 <= off < self.size else None


@dataclass(frozen=True)
class Layout:
    rom_sha1: str
    entry: int
    overlay_table: int
    segments: tuple[Segment, ...]

    @property
    def residents(self) -> tuple[Segment, ...]:
        return tuple(s for s in self.segments if not s.overlay)

    def views(self) -> dict[str, tuple[Segment, ...]]:
        """One address space per overlay: the residents plus that overlay."""
        return {s.name.removeprefix("ovl_"): self.residents + (s,) for s in self.segments if s.overlay}

    def segment_at_rom(self, rom: int) -> Segment:
        return next(s for s in self.segments if s.holds_rom(rom))


def load_layout(path: Path = ROOT / "segments.toml") -> Layout:
    raw = tomllib.loads(path.read_text())
    segs = []
    for s in raw["segment"]:
        seg = Segment(s["name"], *s["rom"], s["vram"], *s["bss"], s.get("overlay", False), s.get("table_index"))
        if seg.vram + seg.size != seg.bss_start or seg.bss_end < seg.bss_start:
            raise ValueError(f"{seg.name}: vram + size must equal bss_start")
        segs.append(seg)
    return Layout(raw["rom_sha1"], raw["entry"], raw["overlay_table"], tuple(segs))


@dataclass(frozen=True)
class Symbol:
    name: str
    vram: int
    kind: str
    rom: int | None


SYMBOL_LINE = re.compile(r"^(\w+)\s*=\s*(0x[0-9A-Fa-f]+);\s*(?://(.*))?$")


def load_symbols(path: Path = ROOT / "symbols.txt") -> list[Symbol]:
    """splat symbol_addrs format: `name = 0xVRAM; // type:func rom:0xOFFSET`. rom: is required inside overlays."""
    out = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        m = SYMBOL_LINE.match(line)
        if not m:
            raise ValueError(f"symbols.txt:{n}: unparsable line: {line}")
        attrs = dict(a.split(":", 1) for a in (m.group(3) or "").split() if ":" in a)
        rom = int(attrs["rom"], 0) if "rom" in attrs else None
        out.append(Symbol(m.group(1), int(m.group(2), 0), attrs.get("type", "func"), rom))
    return out
