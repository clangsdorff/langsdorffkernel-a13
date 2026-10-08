#!/usr/bin/env python3
# usage: sec2lsi_patch.py <A14 lib64/libsec2lsi_conversion.so> <A13 lib/libsec2lsi_conversion.so> <out>
# A14 masters only match A14 module ids, so LSC stayed unconverted and the A13 DDK asserted; refill them with the A13 masters
import hashlib
import struct
import sys

A14_SHA256 = 'c840fb006759312aa6c9ddc05ecce40f8a1485131c62e9fe7340c000daf9f71d'
A13_SHA256 = 'ba0e090ad91a51a9ca24178b844a8da47b91d4047ccc55bcfa68aacc781a9863'

BLK1 = 0x19e9
BLK2 = 0x1fe8
BLK2_141 = 0x468

# A14 file offsets (.data vaddr - 0x1000)
WIDE = 0x5050
UWIDE = 0xc400
MACRO = 0x137b0
FRONT = 0x1ab60
DUAL_SIZE = 29616
SINGLE_SIZE = 8664

# index 2 (A13 UW, 141 points) and 4 (A13 front, 1021 points) swap the A14 single and dual table paths
SIZEINFO_JT = 0x4160
MASTERINFO_JT = 0x4165
FRONT_RET = 0x1b38


def mov_w9(imm):
    return 0x52800009 | imm << 5


src14, src13, dst = sys.argv[1:4]
d = bytearray(open(src14, 'rb').read())
a13 = open(src13, 'rb').read()
if hashlib.sha256(d).hexdigest() != A14_SHA256:
    sys.exit('%s: not the A145FXXSEDZF2 libsec2lsi_conversion.so' % src14)
if hashlib.sha256(a13).hexdigest() != A13_SHA256:
    sys.exit('%s: not the A13 stock libsec2lsi_conversion.so' % src13)


def expect(off, old):
    if d[off:off + len(old)] != old:
        sys.exit('%s: 0x%x is %s, expected %s' % (src14, off, d[off:off + len(old)].hex(), old.hex()))


def a13_master(off, n):
    blk = a13[off:off + n]
    if n == BLK1 and blk[:4] != b'\x01\x0d\xc8\x19':
        sys.exit('%s: no master header at 0x%x' % (src13, off))
    return blk


def dual(base, mid, blk1, blk2):
    d[base:base + DUAL_SIZE] = bytes(DUAL_SIZE)
    d[base:base + 6] = mid
    d[base + 0xc:base + 0xc + BLK1] = a13_master(blk1, BLK1)
    d[base + 0x33e0:base + 0x33e0 + BLK2] = a13_master(blk2, BLK2)


def single(base, mid, blk1, blk2, n2):
    d[base:base + SINGLE_SIZE] = bytes(SINGLE_SIZE)
    d[base:base + 6] = mid
    d[base + 6:base + 6 + BLK1] = a13_master(blk1, BLK1)
    d[base + 0x19f0:base + 0x19f0 + n2] = a13_master(blk2, n2)


expect(WIDE, b'D50EL\0D50EF\0')
expect(UWIDE, b'Z05EL\0B05EL\0')
expect(MACRO, b'J02EG\0J02EC\0')
expect(FRONT, b'L13EF\0')
expect(SIZEINFO_JT, bytes([0, 28, 6, 3, 20]))
expect(MASTERINFO_JT, bytes([0, 50, 6, 3, 33]))
expect(FRONT_RET, struct.pack('<I', mov_w9(0xfd)))

# A13 GetSizeInfo master sources: A50EL 0x5118/0x6b08, T05EG 0x8af0/0xa4e0, G02EG 0xa948/0xc338, V08EG 0xe320/0xfd10
dual(WIDE, b'A50EL\0', 0x5118, 0x6b08)
dual(MACRO, b'G02EG\0', 0xa948, 0xc338)
dual(UWIDE, b'V08EG\0', 0xe320, 0xfd10)
single(FRONT, b'T05EG\0', 0x8af0, 0xa4e0, BLK2_141)
d[SIZEINFO_JT:SIZEINFO_JT + 5] = bytes([0, 28, 20, 3, 6])
d[MASTERINFO_JT:MASTERINFO_JT + 5] = bytes([0, 50, 33, 3, 6])
struct.pack_into('<I', d, FRONT_RET, mov_w9(0x8d))

open(dst, 'wb').write(d)
print('%s: A13 master tables for A50EL, T05EG, G02EG, V08EG' % src14)
