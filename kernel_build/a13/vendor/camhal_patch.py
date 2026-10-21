#!/usr/bin/env python3
# usage: camhal_patch.py <A14 lib64/libexynoscamera3.so> <out>
# A14 sensor factory knows only A14 ids: the A13-absent cases (211, 221, 222) become GC5035, GC02M1, GC08A3
# fasten AE (120 fps start-up mode) is off for HI1336, which wraps GC08A3: GC08A3 has no 120 fps mode
# HI1336 keeps the GC08A3 Base sensor, size and crop preview tables; its crop and full picture lists get GC08A3 sizes
import hashlib
import struct
import sys

SHA256 = '25dcd8e8b215d600c62922e9326a8177952e9b6fdbb16fd4737976f7ded7bb94'

HI1336 = 0xf2a90
HI556 = 0xf26c0
GC02M2 = 0xf2398
GC5035_BASE = 0x124a70
GC02M1_BASE = 0x126cf8
GC08A3_BASE = 0x128adc
HI1336_BASE = 0x1254a8
HI556_BASE = 0x1259b8
GC02M2_BASE = 0x1271d8
NOP = 0xd503201f


def cmp_w20(imm):
    return 0x7100029f | imm << 10


def mov_w2(imm):
    return 0x52800002 | imm << 5


def mov_w9(imm):
    return 0x52800009 | imm << 5


def strb_fasten_ae(rt):
    return 0x391f0260 | rt


def bl(pc, target):
    return 0x94000000 | ((target - pc) >> 2) & 0x3ffffff


PATCHES = [
    (0xf2054, cmp_w20(220), cmp_w20(213)),
    (0xf2064, cmp_w20(211), cmp_w20(210)),
    (0xf20e0, mov_w2(211), mov_w2(210)),
    (0xf20e8, bl(0xf20e8, HI1336), bl(0xf20e8, HI556)),
    (0xf2098, cmp_w20(221), cmp_w20(214)),
    (0xf214c, mov_w2(221), mov_w2(214)),
    (0xf2154, bl(0xf2154, HI556), bl(0xf2154, GC02M2)),
    (0xf20a0, cmp_w20(222), cmp_w20(219)),
    (0xf2104, mov_w2(222), mov_w2(219)),
    (0xf210c, bl(0xf210c, GC02M2), bl(0xf210c, HI1336)),
    (0xf2aac, bl(0xf2aac, HI1336_BASE), bl(0xf2aac, GC08A3_BASE)),
    (0xf26d8, bl(0xf26d8, HI556_BASE), bl(0xf26d8, GC5035_BASE)),
    (0xf23c4, bl(0xf23c4, GC02M2_BASE), bl(0xf23c4, GC02M1_BASE)),
    (0xf2ba4, strb_fasten_ae(10), strb_fasten_ae(31)),
    (0xf2bf0, mov_w9(5), mov_w9(4)),
    (0xf2ae0, 0xfd00ee60, NOP),
    (0xf2aec, 0xf9000109, NOP),
    (0xf2af8, 0xf9050a68, NOP),
    (0xf2b04, 0xf904ae68, NOP),
    (0xf2b10, 0xf9050e68, NOP),
    (0xf2b1c, 0xfd047260, NOP),
    (0xf2b34, 0xf902c668, NOP),
    (0xf2b40, 0xf904aa6a, NOP),
    (0xf2b54, 0xf902ca68, NOP),
    (0xf2b80, 0xfd02da60, NOP),
    (0xf2bb8, 0x3d8002a1, NOP),
    (0xf2c00, 0xb9090a69, NOP),
    (0xf2c0c, 0xf904fa69, NOP),
]

TABLES = [
    (0x28f6dc,
     (3712, 2556, 33331760, 15, 3408, 2556, 33331760, 1,
      3712, 2088, 33331760, 0, 3712, 1668, 33331760, 13),
     (2640, 1980, 33331760, 1, 2880, 1620, 33331760, 0,
      2880, 1296, 33331760, 13, 1968, 1968, 33331760, 2)),
    (0x28f72c,
     (3712, 2556, 50000000, 15, 3408, 2556, 50000000, 1,
      3712, 2088, 50000000, 0, 3712, 1668, 50000000, 13),
     (2640, 1980, 50000000, 1, 2880, 1620, 50000000, 0,
      2880, 1296, 50000000, 13, 1968, 1968, 50000000, 2)),
    (0x28f77c,
     (3264, 2448, 50000000, 1, 3264, 1836, 50000000, 0, 3264, 1468, 50000000, 13,
      2608, 1956, 50000000, 1, 2608, 1468, 50000000, 0, 2608, 1172, 50000000, 13,
      1968, 1968, 50000000, 2),
     (3264, 2448, 50000000, 1, 3264, 1836, 50000000, 0, 3264, 1472, 50000000, 13,
      2448, 2448, 50000000, 2, 2608, 1956, 50000000, 1, 2608, 1468, 50000000, 0,
      1968, 1968, 50000000, 2)),
]

src, dst = sys.argv[1], sys.argv[2]
d = bytearray(open(src, 'rb').read())
if hashlib.sha256(d).hexdigest() != SHA256:
    sys.exit('%s: not the A145FXXSEDZF2 libexynoscamera3.so' % src)
for off, old, new in PATCHES:
    cur = struct.unpack_from('<I', d, off)[0]
    if cur != old:
        sys.exit('%s: 0x%x is 0x%08x, expected 0x%08x' % (src, off, cur, old))
    struct.pack_into('<I', d, off, new)
for off, old, new in TABLES:
    fmt = '<%di' % len(old)
    if struct.unpack_from(fmt, d, off) != old:
        sys.exit('%s: table at 0x%x differs' % (src, off))
    struct.pack_into(fmt, d, off, *new)
open(dst, 'wb').write(d)
print('%s: %d instructions, %d tables patched' % (src, len(PATCHES), len(TABLES)))
