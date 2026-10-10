#!/usr/bin/env python3
# usage: camhal_patch.py <A14 lib64/libexynoscamera3.so> <out>
# A14 sensor factory knows only A14 ids: the A13-absent cases (210, 214, 219) become GC5035, GC02M1, GC08A3
# fasten AE (120 fps start-up mode) is off for HI1336, which wraps GC08A3: GC08A3 has no 120 fps mode
import hashlib
import struct
import sys

SHA256 = 'dc96e27245232ffd2ff0771c339f069feeec19df1c484b3db7eb5658ce64af55'

GC5035_BASE = 0x128cb8
GC02M1_BASE = 0x12aebc
GC08A3_BASE = 0x12cc40
HI1336_BASE = 0x1296b8
HI556_BASE = 0x129ba8
GC02M2_BASE = 0x12b388

# sensor id - 0xd3 indexes this byte table of (target - 0xf7078) / 4
JUMP_TABLE = 0x70b60
JT_OLD = bytes([0x00, 0x5c, 0x5c, 0x5c, 0x5c, 0x5c, 0x5c, 0x5c, 0x5c, 0x1d, 0x2f, 0x26, 0x5c, 0x14])
JT_NEW = bytes([0x2f, 0x5c, 0x5c, 0x5c, 0x26, 0x5c, 0x5c, 0x5c, 0x5c, 0x00, 0x5c, 0x5c, 0x5c, 0x5c])


def sub_w8_w20(imm):
    return 0x51000288 | imm << 10


def mov_w2(imm):
    return 0x52800002 | imm << 5


def strb_fasten_ae(rt):
    return 0x391f0260 | rt


def bl(pc, target):
    return 0x94000000 | ((target - pc) >> 2) & 0x3ffffff


PATCHES = [
    (0xf7054, sub_w8_w20(211), sub_w8_w20(210)),
    (0xf7084, mov_w2(211), mov_w2(219)),
    (0xf711c, mov_w2(222), mov_w2(214)),
    (0xf7140, mov_w2(221), mov_w2(210)),
    (0xf7ad4, bl(0xf7ad4, HI1336_BASE), bl(0xf7ad4, GC08A3_BASE)),
    (0xf76f4, bl(0xf76f4, HI556_BASE), bl(0xf76f4, GC5035_BASE)),
    (0xf73b8, bl(0xf73b8, GC02M2_BASE), bl(0xf73b8, GC02M1_BASE)),
    (0xf7bc0, strb_fasten_ae(9), strb_fasten_ae(31)),
]

src, dst = sys.argv[1], sys.argv[2]
d = bytearray(open(src, 'rb').read())
if hashlib.sha256(d).hexdigest() != SHA256:
    sys.exit('%s: not the A145FXXS9CYE1 libexynoscamera3.so' % src)
for off, old, new in PATCHES:
    cur = struct.unpack_from('<I', d, off)[0]
    if cur != old:
        sys.exit('%s: 0x%x is 0x%08x, expected 0x%08x' % (src, off, cur, old))
    struct.pack_into('<I', d, off, new)
if d[JUMP_TABLE:JUMP_TABLE + len(JT_OLD)] != JT_OLD:
    sys.exit('%s: sensor id jump table at 0x%x differs' % (src, JUMP_TABLE))
d[JUMP_TABLE:JUMP_TABLE + len(JT_NEW)] = JT_NEW
open(dst, 'wb').write(d)
print('%s: %d instructions and the sensor id table patched' % (src, len(PATCHES)))
