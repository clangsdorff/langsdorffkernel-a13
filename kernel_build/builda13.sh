#!/bin/bash

VARIANT="${VARIANT:-e}"
if [ -z "$XY_TAG" ]; then
    XY_TAG=$(git describe --tags --abbrev=0)
fi
XY_VERSION="@a13-${XY_TAG}${VARIANT}"
if [ "$(git branch --show-current)" = "no-oc-root" ]; then
    XY_VERSION="${XY_VERSION}n"
fi

set -e

if [ -z "$1" ]; then
    echo "Please exec from root directory"
    exit 1
fi
cd "$1"

if [ "$(uname -m)" != "x86_64" ]; then
  echo "This script requires an x86_64 (64-bit) machine."
  exit 1
fi

if [ "$VARIANT" = "p" ]; then
    DEFCONFIG="${DEFCONFIG:-a13noavbp_defconfig}"
else
    DEFCONFIG="${DEFCONFIG:-a13noavb_defconfig}"
fi

OUTDIR="$(pwd)/out"
MODULES_OUTDIR="$(pwd)/modules_out"
TMPDIR="$(pwd)/kernel_build/tmp"
A13DIR="$(pwd)/kernel_build/a13"

IN_DTB="$OUTDIR/arch/arm64/boot/dts/exynos/s5e3830.dtb"
IN_DTBO_R00="$OUTDIR/arch/arm64/boot/dts/samsung/a13/a13_eur_open_w00_r00.dtbo"
IN_DTBO_R06="$OUTDIR/arch/arm64/boot/dts/samsung/a13/a13_eur_open_w00_r06.dtbo"
A14_LOAD="$(pwd)/kernel_build/vboot_dlkm/modules.load"

RAMDISK_DIR="$TMPDIR/ramdisk"

MKBOOTIMG="$(pwd)/kernel_build/mkbootimg/mkbootimg.py"
MKDTBOIMG="$(pwd)/kernel_build/dtb/mkdtboimg.py"
AVBTOOL="$(pwd)/kernel_build/avbtool"
AVB_KEY="${AVB_KEY:-$(pwd)/kernel_build/mkbootimg/gki/testdata/testkey_rsa4096.pem}"

OUT_NAME="langsdorff${XY_VERSION}"
OUT_ZIP="$(pwd)/kernel_build/${OUT_NAME}.zip"
OUT_TAR="$(pwd)/kernel_build/${OUT_NAME}.tar"
OUT_KERNEL="$OUTDIR/arch/arm64/boot/Image"
OUT_BOOTIMG="$TMPDIR/boot.img"
OUT_DTBOIMG="$TMPDIR/dtbo.img"
OUT_DTBIMAGE="$TMPDIR/dtb.img"

# A13 boot partition, from the stock boot.img dump
BOOT_PART_SIZE=46137344
DTBO_PART_SIZE=8388608

GIT_COMMIT=$(git rev-parse --short HEAD)
BUILD_ARGS=(LOCALVERSION=-langsdorff-${XY_VERSION#@}-${GIT_COMMIT} KBUILD_BUILD_USER=Langsdorff KBUILD_BUILD_HOST=langsdorff)
command -v ccache >/dev/null && BUILD_ARGS+=("CC=ccache clang")

DIR="$(readlink -f .)"
PARENT_DIR="$(readlink -f ${DIR}/..)"

export CROSS_COMPILE="$PARENT_DIR/clang-r450784d/bin/aarch64-linux-gnu-"
export CC="$PARENT_DIR/clang-r450784d/bin/clang"
export PATH="$PARENT_DIR/build-tools/path/linux-x86:$PARENT_DIR/clang-r450784d/bin:$PATH"
export LLVM_LDFLAGS="-fuse-ld=mold"
export LD="mold"
export DTC_FLAGS="-@"
export PLATFORM_VERSION=14
export LLVM=1
export DEPMOD=depmod
export ARCH=arm64
export TARGET_SOC=s5e3830

rm -rf "$TMPDIR" "$MODULES_OUTDIR"

make -j$(nproc --all) -C $(pwd) LDFLAGS="-fuse-ld=mold" O=out "${BUILD_ARGS[@]}" $DEFCONFIG
make -j$(nproc --all) -C $(pwd) LDFLAGS="-fuse-ld=mold" O=out "${BUILD_ARGS[@]}" dtbs
make -j$(nproc --all) -C $(pwd) LDFLAGS="-fuse-ld=mold" O=out "${BUILD_ARGS[@]}"
make -j$(nproc --all) -C $(pwd) LDFLAGS="-fuse-ld=mold" O=out "${BUILD_ARGS[@]}" INSTALL_MOD_STRIP="--strip-debug --keep-section=.ARM.attributes" INSTALL_MOD_PATH="$MODULES_OUTDIR" modules_install

mkdir -p "$TMPDIR" "$RAMDISK_DIR"

# Every module is loaded by first stage init from the ramdisk, so a kernel update needs no vendor flash
KVER=$(ls "$MODULES_OUTDIR/lib/modules")
KMODS="$MODULES_OUTDIR/lib/modules/$KVER"
python3 "$A13DIR/split_modules.py" "$KMODS" "$A14_LOAD" "$A13DIR/modules_extra.load" "$TMPDIR/first.load"

mkdir -p "$RAMDISK_DIR/lib/modules/0.0"
for m in $(cat "$TMPDIR/first.load"); do
    cp -f "$(find "$KMODS" -name "$m")" "$RAMDISK_DIR/lib/modules/0.0/$m"
done
cp -f "$TMPDIR/first.load" "$RAMDISK_DIR/lib/modules/0.0/modules.order"
cp -f "$OUTDIR/modules.builtin" "$RAMDISK_DIR/lib/modules/0.0/modules.builtin"
depmod 0.0 -b "$RAMDISK_DIR"
sed -i 's/\([^ ]\+\)/\/lib\/modules\/\1/g' "$RAMDISK_DIR/lib/modules/0.0/modules.dep"
mv "$RAMDISK_DIR/lib/modules/0.0"/* "$RAMDISK_DIR/lib/modules/"
rmdir "$RAMDISK_DIR/lib/modules/0.0"
find "$RAMDISK_DIR/lib/modules" -name "modules.*" ! -name modules.dep ! -name modules.softdep ! -name modules.alias -delete
cp -f "$TMPDIR/first.load" "$RAMDISK_DIR/lib/modules/modules.load"

cp -a "$A13DIR/ramdisk/." "$RAMDISK_DIR/"
# Touch, grip and sensorhub drivers request their firmware at probe, before /vendor is mounted
cp -a "$A13DIR/vendor/vendor_overlay/firmware" "$RAMDISK_DIR/lib/firmware"
for d in debug_ramdisk dev metadata mnt proc second_stage_resources sys first_stage_ramdisk; do
    mkdir -p "$RAMDISK_DIR/$d"
done
chmod 750 "$RAMDISK_DIR/init"
chmod 755 "$RAMDISK_DIR/system/bin/snapuserd_ramdisk"
cp -f "$A13DIR/fstab.s5e3830" "$RAMDISK_DIR/fstab.s5e3830"
cp -f "$A13DIR/fstab.s5e3830" "$RAMDISK_DIR/first_stage_ramdisk/fstab.s5e3830"
chmod 640 "$RAMDISK_DIR/fstab.s5e3830" "$RAMDISK_DIR/first_stage_ramdisk/fstab.s5e3830"

(cd "$RAMDISK_DIR" && find . | sort | cpio --quiet -o -H newc -R root:root | zstd -19 -q -c > "$TMPDIR/ramdisk.zst")
echo "ramdisk: $(stat -c %s "$TMPDIR/ramdisk.zst"), kernel: $(stat -c %s "$OUT_KERNEL")"

python2 "$MKDTBOIMG" create "$OUT_DTBIMAGE" --page_size=2048 --version=0 "$IN_DTB" --id=0 --rev=0 --custom0=0x0 --custom1=0xff
python2 "$MKDTBOIMG" create "$OUT_DTBOIMG" --page_size=2048 --version=0 \
    "$IN_DTBO_R00" --id=0 --rev=0 --custom0=0x0 --custom1=0x5 \
    "$IN_DTBO_R06" --id=0 --rev=0 --custom0=0x6 --custom1=0x20

# Layout matches the stock A13 boot.img; os_version/patch must stay equal to stock for KeyMint
$MKBOOTIMG --header_version 2 \
    --kernel "$OUT_KERNEL" \
    --ramdisk "$TMPDIR/ramdisk.zst" \
    --dtb "$OUT_DTBIMAGE" \
    --base 0x10000000 --kernel_offset 0x00008000 --ramdisk_offset 0x01000000 \
    --tags_offset 0x00000100 --dtb_offset 0x00000000 --pagesize 2048 \
    --board SRPUK09B014 \
    --cmdline "androidboot.hardware=s5e3830 loop.max_part=7" \
    --os_version 14.0.0 --os_patch_level 2026-02 \
    --output "$OUT_BOOTIMG"

BOOT_SIZE=$(stat -c %s "$OUT_BOOTIMG")
echo "boot.img: $BOOT_SIZE / $BOOT_PART_SIZE"
if [ "$BOOT_SIZE" -gt "$BOOT_PART_SIZE" ]; then
    echo "ERROR: boot.img does not fit the A13 boot partition"
    exit 1
fi

python3 "$AVBTOOL" add_hash_footer --image "$OUT_BOOTIMG" --partition_name boot \
    --partition_size $BOOT_PART_SIZE --algorithm SHA256_RSA4096 --key "$AVB_KEY"
python3 "$AVBTOOL" add_hash_footer --image "$OUT_DTBOIMG" --partition_name dtbo \
    --partition_size $DTBO_PART_SIZE --algorithm SHA256_RSA4096 --key "$AVB_KEY"

rm -f "$OUT_ZIP" "$OUT_TAR"
mkdir -p "$TMPDIR/zip/META-INF/com/google/android"
cp -f "$(pwd)/kernel_build/zip/META-INF/com/google/android/update-binary" "$TMPDIR/zip/META-INF/com/google/android/"
cp -f "$A13DIR/update-commands" "$TMPDIR/zip/META-INF/com/google/android/update-commands"
brotli --quality=6 -c "$OUT_BOOTIMG" > "$TMPDIR/zip/boot.br"
brotli --quality=6 -c "$OUT_DTBOIMG" > "$TMPDIR/zip/dtbo.br"
(cd "$TMPDIR/zip" && zip -r9 -q "$OUT_ZIP" META-INF boot.br dtbo.br)

(cd "$TMPDIR" && for f in boot.img dtbo.img; do lz4 -c -12 -B6 --content-size "$f" > "$f.lz4"; done \
    && tar -cf "$OUT_TAR" boot.img.lz4 dtbo.img.lz4)

echo "Done: $OUT_ZIP $OUT_TAR"
rm -rf "$MODULES_OUTDIR"
