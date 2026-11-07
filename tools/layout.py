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
    text_end: int
    bss_start: int
    bss_end: int
    overlay: bool
    table_index: int | None

    @property
    def size(self) -> int:
        return self.rom_end - self.rom_start

    @property
    def text_rom_end(self) -> int:
        return self.rom_start + self.text_end - self.vram

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
        seg = Segment(s["name"], *s["rom"], s["vram"], s["text_end"], *s["bss"], s.get("overlay", False), s.get("table_index"))
        if not seg.vram < seg.text_end <= seg.bss_start == seg.vram + seg.size <= seg.bss_end:
            raise ValueError(f"{seg.name}: need vram < text_end <= bss_start == vram + size <= bss_end")
        segs.append(seg)
    return Layout(raw["rom_sha1"], raw["entry"], raw["overlay_table"], tuple(segs))


@dataclass(frozen=True)
class Symbol:
    name: str
    vram: int
    kind: str
    rom: int | None


SYMBOL_LINE = re.compile(r"^(\w+)\s*=\s*(0x[0-9A-Fa-f]+);\s*(?://(.*))?$")


def load_symbols() -> list[Symbol]:
    """Every symbols*.txt in splat symbol_addrs format: `name = 0xVRAM; // type:func rom:0xOFFSET`.

    rom: is required inside overlays. A name defined twice is an error.
    """
    out = []
    for path in sorted(ROOT.glob("symbols*.txt")):
        out += parse_symbols(path)
    dupes = {s.name for s in out if sum(t.name == s.name for t in out) > 1}
    if dupes:
        raise ValueError(f"symbols defined twice: {sorted(dupes)}")
    return out


def parse_symbols(path: Path) -> list[Symbol]:
    out = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        m = SYMBOL_LINE.match(line)
        if not m:
            raise ValueError(f"{path.name}:{n}: unparsable line: {line}")
        attrs = dict(a.split(":", 1) for a in (m.group(3) or "").split() if ":" in a)
        rom = int(attrs["rom"], 0) if "rom" in attrs else None
        out.append(Symbol(m.group(1), int(m.group(2), 0), attrs.get("type", "func"), rom))
    return out
