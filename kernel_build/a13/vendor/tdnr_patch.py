#!/usr/bin/env python3
# usage: tdnr_patch.py <A14 lib64/libexynoscamera_tdnr_plugin.so> <out>
# The TDNR plugin hands libmfb a hardcoded "a14" project, whose sensor list has no GC5035 (210) or GC08A3 (219):
# MFB init fails and checkSkipFlag later reads the uninitialized instance. libmfb has an "a13" project with
# S5KJN1, GC5035, GC08A3 and GC02M1, so the plugin passes "a13"
import hashlib
import struct
import sys

SHA256 = 'f44bd771066d8717c17e9653cc8ca2606a4a5dd23b5d5bb65849f23b991209c9'

PATCHES = [
    (0x3030, 0x72a00689, 0x72a00669),  # movk w9, #0x34, lsl #16 -> #0x33 ("a14" -> "a13")
]

src, dst = sys.argv[1], sys.argv[2]
d = bytearray(open(src, 'rb').read())
if hashlib.sha256(d).hexdigest() != SHA256:
    sys.exit('%s: not the A145FXXSEDZF2 libexynoscamera_tdnr_plugin.so' % src)
for off, old, new in PATCHES:
    cur = struct.unpack_from('<I', d, off)[0]
    if cur != old:
        sys.exit('%s: 0x%x is 0x%08x, expected 0x%08x' % (src, off, cur, old))
    struct.pack_into('<I', d, off, new)
open(dst, 'wb').write(d)
print('%s: %d instructions patched' % (src, len(PATCHES)))
