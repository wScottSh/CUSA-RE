# Cruis'n USA runtime architecture

How the game's code is organized at runtime. Each claim cites an address and its evidence.

Evidence tags:

- **[code]** decompiled pseudocode in `build/c/<view>/functions/0xADDR.c`, or objdump disassembly of the ROM.
- **[log N]** line N of `build/rt/game.pilog` (boot-to-race PI DMA log; cart = 0x10000000 + ROM offset).
- **[rom]** bytes read from `ROM/Cruis'n USA.z64`.
- **inferred** means the reading fits the code but nothing confirmed it.

Names in `code font` are in `symbols.txt` or `symbols.lib.txt`. Bare `FUN_`/`DAT_` addresses are unnamed.

## 1. Boot

`entry` (0x80100000) [code]:

1. Zeroes BSS 0x8013C860..0x80165840 (0x28FE0 bytes, 8 per loop).
2. Sets `sp` = 0x8013C960 and jumps to 0x80100050.
3. 0x80100050 calls `osInitialize` (0x8011F990). That function writes the exception-vector stubs at 0x80000000/0x80000080 and pokes PIF RAM 0x1FC007FC, the libultra pattern.
4. It creates thread 1 (`idle_thread`) and starts it.

`idle_thread` (0x801000A8) [code]:

1. Calls `osCreatePiManager(150, cmdQ 0x8013F990, cmdBuf 0x8013F670, 200)` at 0x801000C8.
2. Creates and starts thread 2 (`main_thread`) at 0x801000F8.
3. Spins forever at 0x8010010C (`b .`). Its priority is 0, so it only runs when every other thread blocks.

`main_thread` (0x80100124) [code]:

1. Writes the memory map into globals 0x80146588..0x801465F8 (see Memory map below).
2. Creates the DMA queue 0x801474B0 and thread 3 (`dma_thread`).
3. `ovl_load(0)` at 0x8010030C loads ovl_boot.
4. Calls `boot_init` (ovl_boot 0x80025C80) at 0x80100314.
5. `ovl_unload(0)` at 0x8010031C gives back ovl_boot's heap bytes.
6. `main_loop` (0x801111E0) at 0x80100324 never returns.

`boot_init` (ovl_boot 0x80025C80) [code]:

- Fills the 3 graphics-slot descriptors at 0x801476A0 and the 3 framebuffer entries at 0x80147730.
- Builds the graphics `OSTask` at 0x80147620. Its fields: type 1, ucode_boot 0x8012F520 (0xD0 bytes), ucode 0x8012F5F0 (0x1000), ucode_data 0x8013BDA0 (0x800), dram_stack 0x80146180 (0x400), output buffer 0x803B6C00..0x803BEC00, yield 0x8014BDA0 (0x900).
- Calls `osCreateViManager(0xFE)` and `osViSetMode`, probes controllers, creates the message queues and threads 6, 7, 4 and 5, and clears the framebuffers (0x9600 words = 320x240x2 bytes each).
- Calls `audio_init` (0x8002692C), which runs `alHeapInit(0x801466D8, 0x803BEC00, 0x41400)` and opens the audio banks at ROM 0x5C40D0 and 0x72AD50.
- Ends by setting `DAT_8014c6c8 = 0x8003` and frame callback `DAT_8014c6c0 = 0x8003F130`. That requests ovl_frontend (section 3).

### osCreateThread calls

Every `jal osCreateThread` in all four non-main segments was grepped; there are none outside main and ovl_boot [code]. Stack is the top of stack (5th argument). Priority is the 6th argument.

| id | OSThread | entry | pri | stack top | call site |
|---|---|---|---|---|---|
| 1 | 0x8013C960 | `idle_thread` 0x801000A8 | 0 | 0x8013D710 | 0x80100084 |
| 2 | 0x8013E8C0 | `main_thread` 0x80100124 | 10 | 0x8013F670 | 0x801000F8 (idle) |
| 3 | 0x80146700 | `dma_thread` 0x801036FC | 50 | 0x801474B0 | 0x801002F8 (main) |
| 0 | 0x80162F60 | `__osDevMgrMain` 0x80125740 (PI) | 150 | 0x80164110 | 0x8011FF94 (`osCreatePiManager`) |
| 0 | 0x80164130 | 0x80120194 (VI manager) | 254 | 0x801652E0 | 0x80120144 (`osCreateViManager`) |
| 6 | 0x80147748 | `sched_thread` 0x80103E48 | 90 | 0x801484F8 | ovl_boot 0x80026118 |
| 7 | 0x80148558 | `fault_thread` 0x801047AC | 40 | 0x80149308 | ovl_boot 0x80026154 |
| 4 | 0x8014C6E0 | `cont_thread` 0x80111EC0 | 70 | 0x8014D490 | ovl_boot 0x80026190 |
| 5 | 0x8014D490 | `cont_poll_thread` 0x80111DCC | 80 | 0x8014E240 | ovl_boot 0x800261CC |

The PI and VI manager priorities come from their callers (150 at 0x801000C4, 0xFE passed by `boot_init`).

## 2. Threads, queues, and the frame loop

### Threads

- **`dma_thread`** (0x801036FC) [code]. Blocks on queue 0x801474B0, the PI completion queue passed to `osPiStartDma` at 0x801038C4. On each message it marks the current request done (flag 0x8000 at +0x18). It queues the request for its callback (`FUN_80111150`, list 0x8014C6B0), then starts the next request. The high-priority list is 0x801474F0 and the normal list is 0x801474E8.
- **`sched_thread`** (0x80103E48) [code]. Blocks on queue 0x80146660 (20 messages). It dispatches on the message value:
  - 1 = SP done (`osSetEventMesg(4, ..., 1)`), handled by 0x80103F08.
  - 2 = DP done (event 9), handled by 0x80104038.
  - 3 = VI retrace (`osViSetEvent(q, 3, 1)`), handled by `sched_retrace` 0x801040A4.
  - 4 = sent by `osSendMesg(q, 4)` in 0x801043BC, handled by 0x80104228. The task-ready meaning is inferred.
  - 5 = PRENMI (event 14), handled by `sched_prenmi` 0x80104384, which sets `DAT_80147680 = 1` and blanks video.
  - `sched_retrace` swaps among the 3 framebuffers and builds an extra task every second retrace (`FUN_80105bc4`). 0x80103F08 calls `osSpTaskYielded` on the gfx task, so that extra task preempts graphics. The guess that it is the audio task is inferred.
- **`fault_thread`** (0x801047AC) [code]. Waits once on 0x80149308, which is bound to OS_EVENT_FAULT (12) in `boot_init`, then spins.
- **`cont_thread`** (0x80111EC0) [code]. Waits on the SI queue 0x80146620 (event 5). It calls 0x80111FF8, which runs `osContGetReadData` into 0x8014E250 and copies buttons and stick into per-pad state at 0x8014E300.
- **`cont_poll_thread`** (0x80111DCC) [code]. Waits on 0x80146640, which `osSetTimer` at 0x80111DB4 targets, then calls `osContStartReadData`.

`int_disable`/`int_restore` (0x801156E0/0x80115700) clear and restore Status.IE. They guard the shared state above [code].

### Frame loop: `main_loop` (0x801111E0) [code]

Each iteration:

1. Spins while `DAT_80147680` (PRENMI flag) is set.
2. Runs DMA completion callbacks (`run_dma_callbacks` 0x80111184).
3. Runs `FUN_8011f780`, which switches the audio sequence (inferred from its callees).
4. Switches overlays if requested (section 3).
5. `gfx_slot_acquire` (0x801039E0) claims one of 3 slots at 0x801476A0 (0x30 bytes each) if a frame credit `DAT_80147660` is left. If no slot is free, it loops again: the main thread busy-polls at priority 10.
6. Emits display-list words (0xBC moveword x4, 0x06 G_DL to 0x80133910) at `DAT_80147684`.
7. Calls the frame callback `(*DAT_8014c6c0)(DAT_8014c6c4)`, which lives in the loaded overlay.
8. Appends G_FULLSYNC (0xE9) and G_ENDDL (0xB8).
9. `gfx_submit` (0x80103B10) checks buffer use against 0x8000 / 64000 / 16000 / 0x140 bytes and hands the slot to the scheduler.

`sched_retrace` adds one frame credit every second retrace, capped at 2. This caps game logic at 30 Hz on NTSC (inferred).

### Memory map (physical; written by `main_thread`, 0x80100124) [code]

| range | use |
|---|---|
| 0x000480..0x00AA50 | `low` segment: asset loader text + BSS (window 0x17F0, entry buffer 0x97F0) |
| 0x025C80.. | overlay slot. Bump heap `DAT_8014658c` starts here (`*0x801465EC = 0x25C80`) |
| ..0x100000 | heap ceiling `DAT_801465f0`. The asset cache also wraps down from here |
| 0x100000..0x165840 | main + BSS |
| 0x165800, 0x18B000, 0x1B0800 | 3 framebuffers, 0x25800 each (`DAT_801465a0`). The first is computed from BSS end |
| 0x1D6000..0x363EC0 | asset cache, top-down (`DAT_801465f4`..`DAT_801465f8`) |
| 0x363EC0..0x3B6C00 | per-slot buffers x3: 0x140, 16000, 64000, 0x8000 (tables 0x801465E0/D0/C0/B0) |
| 0x3B6C00..0x3BEC00 | gfx task output buffer (`OSTask` +0x28/+0x2C) |
| 0x3BEC00..0x400000 | audio heap (0x41400) |

## 3. Overlay loading

Overlay table 0x801321D0 holds 6 words per entry: rom_start, rom_end, vram, vram_end (= bss_end), bss_start, bss_end. `tools/check.py` verifies it against `segments.toml`.

- **`ovl_copy(idx)`** (0x80103264) [code] calls `dma_read(rom_start, vram, rom_end - rom_start, 6)` and then `bzero_words(bss_start, (bss_end - bss_start) / 4)`. Flag 6 = invalidate D-cache (2) + invalidate I-cache (4, `osInvalICache` in `dma_start` 0x801037DC).
- **`ovl_load(idx)`** (0x80102CA0) records the index in `DAT_801466d0`, calls `ovl_copy`, and advances the bump heap `DAT_8014658c` by `ovl_size(idx)` (0x80103238 = vram_end - vram). **`ovl_unload`** (0x80102CE8) subtracts it. `ovl_copy` has exactly two callers: `ovl_load` (0x80102CBC) and `low_reload` (0x80102E4C) [code].
- **`dma_read`** (0x801035D0) [code] builds a request on the stack (+0xC rom, +0x10 dram, +0x14 len, +0x18 flags). It passes it to `dma_enqueue` (0x80103628) and spins until `dma_thread` sets 0x8000. This is the path for every overlay and asset load. `pi_read_sync` (0x801053D4) is a separate direct `osPiStartDma` wrapper on queue 0x801493F8. Its only caller is `FUN_8010c260`, whose callers sit in the audio code at 0x80106xxx/0x80110xxx.

### Who picks the overlay

`main_loop` compares the requested index `DAT_8014c6c8` with the current one `DAT_8014c6cc`. When they differ, it unloads the current overlay (unless 0x7FFF), clears bit 0x8000 of the request, and runs `ovl_load` on it. Requesters set bit 0x8000, so asking for the overlay already loaded still forces a reload. Each requester also sets the frame callback to a function in the target overlay [code]:

| requester | request | callback | evidence |
|---|---|---|---|
| `main_thread` 0x8010030C | ovl_boot (0), direct `ovl_load` | none, `boot_init` called directly | [code], [log 339640] 3728 bytes from 0x3D860 |
| `boot_init` end | 0x8003 ovl_frontend | 0x8003F130 | [code], [log 343284] 0x20700 bytes from 0x5EA10 |
| frontend 0x80027C94, 0x80029DA8, 0x8002BE5C | 0x8002 ovl_race | 0x8002F600 | [code], [log 355536] 0x20320 bytes from 0x3E6F0 |
| race 0x8002ED04 (START, mode 2), 0x8002FE98 | 0x8003 ovl_frontend | 0x80026030 | [code] |
| race 0x8002F7DC | 0x8003 ovl_frontend | 0x80026C98 | [code] |
| race 0x8002F468 (START pressed) | 0x8002 ovl_race again | 0x8002F600 | [code]; restart is inferred |

### `low` reloads

`low_reload` (0x80102D74) [code] spins until neither in-flight gfx slot (`DAT_80147668`, `DAT_8014766c`) has its +0x24 busy word set. Then it calls `ovl_copy(1)`, which re-copies `low` and zeroes its BSS. It has 2 callers in ovl_boot, 2 in ovl_race, 24 in ovl_frontend and 6 in main [code, jal grep]. The log shows 21 loads of 4976 bytes from 0x7F110 to 0x480 in one boot-to-race run, often in back-to-back pairs (e.g. [log 349834], [log 349836]). Why the game reloads it is open (section 5).

### The cross-segment call

`FUN_801141d0` in main (call at 0x8011425C) runs `jal 0x80038B2C` with a0 = 0x801334B0, a1 = float, a2 = 129 [code]. It returns 0x4000/0xC000 on an axis and otherwise scales a lookup by a per-octant table at 0x801336B4. Reading it as a fixed-point atan2 is inferred.

- **ovl_race 0x80038B2C** is a function start: it follows `jr ra` at 0x80038B24. Its body, `table_lerp(float *t, float x, int n)`, clamps x to [0, n-1] and linearly interpolates `t[(int)x]`..`t[(int)x+1]` [code].
- **ovl_frontend 0x80038B2C** is the middle of a function: the instruction there is `sw v0,40(sp)` [code]. Calling it with the frontend loaded would crash.
- `FUN_801141d0`'s only caller is ovl_race 0x80034F2C [code, jal grep over all segments]. The call therefore only happens while ovl_race is resident. `check.py` counts this jal as mapped in the frontend view only because the address lies inside ovl_frontend text.

## 4. ROM data layout

### Asset table, ROM 0x80480..0x98BB4

`asset_load(idx)` (low 0x80000480, disassembly; the Ghidra output drops blocks here) [code]:

1. Calls `asset_find(idx)` (0x80000994) and returns early if the asset is cached.
2. Otherwise `dma_read(0x80484 + idx*8, 0x800097F0, 8, 2)` fetches one 8-byte entry.
3. Allocates the destination and copies the data.

The ROM word at 0x80480 is 0x000030E6 = 12518. Entry 0 points to 0x80480 + 4 + 12518 x 8 = 0x98BB4, so the word is the entry count [rom]. The code never reads it (inferred from its absence in `asset_load`).

Entry format, big-endian (shifts and masks at low 0x800004F0..0x80000560):

| bits | meaning |
|---|---|
| byte0 bit 7 | compressed |
| byte0 bits 6..4 | kind. Kind 2 is allocated with `heap_alloc(size+8, 8)` (0x80102D18, bump heap). The other kinds use `asset_cache_alloc(idx, size)` (0x80000A84). |
| byte0 bits 3..0 | codec. 1 → `FUN_80000c30`/`FUN_80000cb0`. 2..4 → `FUN_80001160`/`FUN_800011f4` with variant codec-2. |
| byte1 low nibble : bytes2..3 | 20-bit size in RAM |
| byte1 high nibble : byte4 | stored size in 256-byte units (12 bits) |
| bytes5..7 | ROM offset from 0x80480 |

- **Uncompressed** entries are one `dma_read(0x80480 + off, dst, size, 2)`.
- **Compressed** entries stream through the window at 0x800017F0 in chunks of at most 0x8000 bytes, with the codec called per chunk. The read is clamped at offset 0x543C50, so assets end at ROM 0x5C40D0 [code].
- After the copy, `FUN_80000b4c(ptr, idx, kind, size)` post-processes the asset. That function was not read.

**Cache.** `asset_cache_alloc` puts an 8-byte header {u16 idx, u16 size/8-1} below each block and grows down from `DAT_80146590` [code]. When the region above the framebuffers fills, it wraps to start below 0x100000. `asset_find` walks those headers. `asset_mark_get`/`asset_mark_set` (0x80000A64/0x80000A74) save and restore `DAT_80146590`. `asset_load_list(idx, out)` (0x8000078C) loads asset idx as a 0xFFFF-terminated u16 list of further indices and loads each one. `boot_init` calls `asset_load_list(700, ...)`.

**Check against runtime** (`tools/assets.py ROM build/rt/game.pilog`): 2516 of 2518 8-byte table reads are immediately followed by a DMA of the decoded ROM address and length (window 0x17F0 with the stored size for compressed entries). In the other 2, a 2 KB read from the sample region lands in between, and the expected asset DMA follows it ([log 356619] then [log 356621]; [log 357563] then [log 357565]). The first table read is entry 0x2BD [log 339662], matching `asset_load(0x2bd)` in `boot_init`. A second run (attract mode only, `build/rt/nav.pilog`) gives 1591 of 1591.

### Region summary [rom, via the decoder]

| region | contents |
|---|---|
| 0x98BB4..0x5C40D0 | 12518 assets, packed in index order (gaps of 0 or 2 bytes, 12508/12517 ascending) |
| 0x5C40D0.. | audio bank, header "SN64" [rom]. `audio_init` passes 0x5C40D0 and 0x5D2BD0. 5 log DMAs |
| 0x5D2BD0..0x72AD50 | sample data (inferred). 861 log DMAs, mostly 2 KB, into the audio heap 0x803BF1E0.. |
| 0x72AD50..0x74E248 | sequence bank, header "SSEQ" [rom], passed by `audio_init`. 165 log DMAs |
| 0x74E248..0x800000 | zero padding [rom] |

Asset counts by kind (compression, kind, codec, count, size range):

- Uncompressed kind 0: 1214 entries, 6..146880 bytes (one has codec 2 set; the codec is ignored when uncompressed).
- Kind 1: 5574 entries, 18..6838 bytes.
- Kind 2: 856 entries, 30..3690 bytes.
- Kind 3: 508 entries, 520..3080 bytes.
- Kind 4: 4361 entries, 16..4104 bytes.
- Compressed kind 0, codec 2: 5 entries, 960..14856 bytes, ROM 0xFED0C..0x108114. All 5 load during boot ([log] to 0x17F0).

Kinds come in 246 interleaved runs across the index space. That suggests per-scene or per-track grouping (inferred).

## 5. Open questions

- **Why `low` reloads.** It has no .data, and `low_reload` first waits for in-flight gfx slots. One reading is that the RSP/RDP or the gfx buffers overwrite 0x480..0xAA50 as scratch (inferred). An RDRAM diff across a frame would confirm it.
- **First framebuffer overlaps BSS.** `main_thread` derives the first framebuffer as (BSS end − 0x80100050 + 0x100000), rounded up to 64 = 0x165800. That is 0x40 below BSS end 0x80165840. Unknown whether the last 0x40 BSS bytes are used.
- **Asset kinds and codecs.** `FUN_80000b4c` (per-kind post-processing) and the codecs at 0x80000C30 and 0x80001160 are unread. No kind is mapped to a format yet.
- **Unnamed pieces.** The `FUN_80105bc4` task (assumed audio) and the senders on queue 0x801475F8 (created by `FUN_801038e0`) are unread. Where `pi_read_sync`'s queue 0x801493F8 is created was not found.
- **`FUN_801141d0`.** The atan2 reading is unconfirmed. Its octant helper `FUN_801142a8` is unread.
