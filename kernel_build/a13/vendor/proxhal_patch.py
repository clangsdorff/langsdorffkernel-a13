#!/usr/bin/env python3
# usage: proxhal_patch.py <A14 lib64/sensors.inputvirtual.so> <out>
# A13 has no proximity chip on the sensorhub, only the touch ear detect behind the Hover Proximity sensor.
# The A14 framework takes the call proximity from type 8 only, so Hover Proximity becomes type 8:
# touch status 0 (far) is reported as 1.0 and 1-3 (near) as 0.0, max range 1.0 puts the threshold at 1.0
import hashlib
import struct
import sys

SHA256 = '5f22568b9817bde52343240e0bc0f71e5747b9bb3a49615c90846c1dfd717f2f'

NOP = 0xd503201f

PATCHES = [
    (0x7f84, 0x528007e4, 0x52800104),  # mov w4, #0x3f -> mov w4, #8
    (0x7fa4, 0x72a00024, NOP),         # movk w4, #1, lsl #16
    (0x7f90, 0x528007f4, 0x52800114),  # mov w20, #0x3f -> mov w20, #8
    (0x7fb0, 0x72a00034, NOP),         # movk w20, #1, lsl #16
    (0x8328, 0x52800029, 0x38386a78),  # mov w9, #1 -> strb w24, [x19, x24]
    (0x832c, 0x38386a69, 0x7100009f),  # strb w9, [x19, x24] -> cmp w4, #0
    (0x8330, 0xbd401500, 0x1a9f17e9),  # ldr s0, [x8, #0x14] -> cset w9, eq
    (0x8334, 0x5e21d800, 0x1e220120),  # scvtf s0, s0 -> scvtf s0, w9
]

# max range, resolution
RANGE = (0x4a78, (9.0, 1.0), (1.0, 1.0))

src, dst = sys.argv[1], sys.argv[2]
d = bytearray(open(src, 'rb').read())
if hashlib.sha256(d).hexdigest() != SHA256:
    sys.exit('%s: not the A145FXXSEDZF2 sensors.inputvirtual.so' % src)
for off, old, new in PATCHES:
    cur = struct.unpack_from('<I', d, off)[0]
    if cur != old:
        sys.exit('%s: 0x%x is 0x%08x, expected 0x%08x' % (src, off, cur, old))
    struct.pack_into('<I', d, off, new)
off, old, new = RANGE
if struct.unpack_from('<2f', d, off) != old:
    sys.exit('%s: range at 0x%x differs' % (src, off))
struct.pack_into('<2f', d, off, *new)
open(dst, 'wb').write(d)
print('%s: %d instructions, range patched' % (src, len(PATCHES)))
