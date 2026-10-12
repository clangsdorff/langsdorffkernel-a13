#!/usr/bin/env python3
# usage: a13hal.py <a13 vendor root> <tree> <bin/hw/...> [...]
# Prints the A13 vendor/lib libraries the binaries need that the tree lacks; exits 1 if a same-named A14 lib dropped a symbol they use.
import os, re, subprocess, sys

SRC, TREE, BINS = sys.argv[1], sys.argv[2], sys.argv[3:]

# provided by the system partition / VNDK on the A14 system, not checked
SYSTEM_LIBS = {
    "libc.so", "libm.so", "libdl.so", "liblog.so", "libc++.so", "libutils.so", "libcutils.so",
    "libbase.so", "libhidlbase.so", "libhidltransport.so", "libhwbinder.so", "libbinder.so",
    "libbinder_ndk.so", "libhardware.so", "libz.so", "libcrypto.so", "libssl.so", "libvndksupport.so",
    "libutilscallstack.so", "libprocessgroup.so", "libjsoncpp.so", "libxml2.so", "libsqlite.so",
    "libexpat.so", "libunwindstack.so", "libbacktrace.so", "libselinux.so", "libnativewindow.so",
    "libsync.so", "libui.so", "libion.so", "libdmabufheap.so", "libvndksupport.so", "libpower.so",
    "android.hidl.base@1.0.so", "android.hidl.manager@1.0.so", "android.hidl.token@1.0.so",
    "android.hidl.allocator@1.0.so", "android.hidl.memory@1.0.so", "libhidlmemory.so",
    "libstagefright_foundation.so", "libcgrouprc.so", "libkeymaster_messages.so",
}

def readelf(args, path):
    return subprocess.run(["readelf", "-W", *args, path], capture_output=True, text=True, check=True).stdout

def needed(path):
    return re.findall(r"\(NEEDED\)\s+Shared library: \[(.+?)\]", readelf(["-d"], path))

def syms(path):
    defined, undefined = set(), set()
    for line in readelf(["--dyn-syms"], path).splitlines():
        f = line.split()
        if len(f) < 8 or not f[0].endswith(":"):
            continue
        name = f[7].split("@")[0]
        if f[4] == "WEAK" and f[6] == "UND":
            continue
        (undefined if f[6] == "UND" else defined).add(name)
    return defined, undefined

def find_lib(name):
    for root in (os.path.join(TREE, "lib"), os.path.join(SRC, "lib")):
        p = os.path.join(root, name)
        if os.path.isfile(p):
            return p
    return None

objs, to_copy, missing = {}, [], []
queue = [os.path.join(SRC, b) for b in BINS]
while queue:
    p = queue.pop()
    if p in objs:
        continue
    objs[p] = needed(p)
    for n in objs[p]:
        if n in SYSTEM_LIBS:
            continue
        lp = find_lib(n)
        if lp is None:
            missing.append(f"{os.path.basename(p)} -> {n}")
            continue
        if lp.startswith(SRC) and n not in to_copy:
            to_copy.append(n)
        queue.append(lp)

if missing:
    print("missing libs: " + ", ".join(missing), file=sys.stderr)
    sys.exit(1)

bad = []
for p in objs:
    for n in objs[p]:
        tree_lib = os.path.join(TREE, "lib", n)
        src_lib = os.path.join(SRC, "lib", n)
        if n in SYSTEM_LIBS or not os.path.isfile(tree_lib) or not os.path.isfile(src_lib):
            continue
        # the A14 copy replaces the A13 one, so it must still export what the A13 copy gave this object
        lost = (syms(src_lib)[0] - syms(tree_lib)[0]) & syms(p)[1]
        bad += [f"{os.path.basename(p)} -> {n}: {s}" for s in lost]

if bad:
    print("A14 libs lack symbols the A13 HAL uses:\n  " + "\n  ".join(sorted(set(bad))[:40]), file=sys.stderr)
    sys.exit(1)

print("\n".join(to_copy))
