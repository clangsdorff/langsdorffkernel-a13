#!/usr/bin/env python3
# usage: ddk_rebase.py <in> <out>
# A13 is_lib.bin/is_rta.bin are linked for the 4.19 LIB_START; 5.10 (VA_BITS 39, no KASAN) maps them at its own LIB_START
import struct
import sys

OLD_BASE = 0xffffff90f9fe0000
NEW_BASE = 0xffffffc101fe0000

src, dst = sys.argv[1], sys.argv[2]
d = bytearray(open(src, 'rb').read())
lo, hi = OLD_BASE, OLD_BASE + 0x6000000
n = 0
for i in range(0, len(d) - 7, 8):
    v = struct.unpack_from('<Q', d, i)[0]
    if lo <= v < hi:
        struct.pack_into('<Q', d, i, v - OLD_BASE + NEW_BASE)
        n += 1
for i in range(len(d) - 7):
    v = struct.unpack_from('<Q', d, i)[0]
    if lo <= v < hi:
        sys.exit('%s: unaligned 4.19 pointer at 0x%x' % (src, i))
if n == 0:
    sys.exit('%s: no 4.19 pointers, not an A13 DDK' % src)
open(dst, 'wb').write(d)
print('%s: %d pointers rebased' % (src, n))
