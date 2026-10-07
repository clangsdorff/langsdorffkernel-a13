#!/bin/bash
# usage: sudo mkvendor_a13.sh <A13 stock vendor.img (f2fs) or its extracted tree> <A14 stock vendor.img (erofs)> <vendor_dlkm.tar.gz> <out.img>
set -euo pipefail

[ $# -eq 4 ] || { sed -n 2p "$0" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "run as root (xattrs, loop mount)" >&2; exit 1; }
for t in fsck.erofs mkfs.erofs dump.erofs setfattr getfattr readelf python3; do
    command -v "$t" >/dev/null || { echo "missing tool: $t" >&2; exit 1; }
done

A13_IMG=$(realpath "$1")
A14_IMG=$(realpath "$2")
DLKM_TAR=$(realpath "$3")
OUT_IMG=$(realpath -m "$4")
KIT=$(dirname "$(realpath "$0")")
OVERLAY=$KIT/vendor_overlay
FSTAB=$KIT/../fstab.s5e3830

WORK=$(mktemp -d /var/tmp/mkvendor_a13.XXXX)
TREE=$WORK/vendor
A13V=$WORK/a13
[ -d "$A13_IMG" ] && A13V=$A13_IMG
cleanup() {
    [ "$A13V" = "$WORK/a13" ] && mountpoint -q "$A13V" && umount "$A13V"
    rm -rf "$WORK"
}
trap cleanup EXIT

label() { setfattr -n security.selinux -v "u:object_r:$1:s0" "$2"; }

mkdir -p "$TREE"
if [ ! -d "$A13_IMG" ]; then
    mkdir -p "$A13V"
    mount -o ro,loop "$A13_IMG" "$A13V"
fi
fsck.erofs --extract="$TREE" --xattrs --preserve --overwrite "$A14_IMG"

a13() { install -D -m "$2" -o 0 -g "$3" "$A13V/$1" "$TREE/$1"; label "$4" "$TREE/$1"; }
a13hal() {
    local exec_label=$1 libs; shift
    libs=$(python3 "$KIT/a13hal.py" "$A13V" "$TREE" "$@") || return 1
    a13 "$1" 755 2000 "$exec_label"
    for l in $libs; do a13 "lib/$l" 644 0 vendor_file; done
}

# Touch, grip and sensorhub firmware that the A13 4.19 kernel had built in
(cd "$OVERLAY/firmware" && find . -type d) | while read -r d; do
    mkdir -p "$TREE/firmware/$d"
    chown 0:0 "$TREE/firmware/$d"; chmod 755 "$TREE/firmware/$d"
    label vendor_fw_file "$TREE/firmware/$d"
done
(cd "$OVERLAY/firmware" && find . -type f) | while read -r f; do
    install -m 644 -o 0 -g 0 "$OVERLAY/firmware/$f" "$TREE/firmware/$f"
    label vendor_fw_file "$TREE/firmware/$f"
done

rm -f "$TREE"/lib/modules/*.ko
mkdir -p "$TREE/vendor_dlkm"
tar -xzf "$DLKM_TAR" -C "$TREE/vendor_dlkm"
chown -R 0:0 "$TREE/vendor_dlkm"
find "$TREE/vendor_dlkm" -type d -exec chmod 755 {} + -exec setfattr -n security.selinux -v u:object_r:vendor_file:s0 {} +
find "$TREE/vendor_dlkm" -type f -exec chmod 644 {} + -exec setfattr -n security.selinux -v u:object_r:vendor_file:s0 {} +

install -m 644 -o 0 -g 0 "$FSTAB" "$TREE/etc/fstab.s5e3830"
label vendor_configs_file "$TREE/etc/fstab.s5e3830"

# A13 has no vendor_dlkm partition; /vendor_dlkm on the A14 system is an empty mount point
sed -i 's#^\(\s*\)exec u:r:vendor_modprobe:s0 -- /vendor/bin/modprobe -a -d /vendor_dlkm/lib/modules input_booster_lkm.ko$#\1exec u:r:vendor_modprobe:s0 -- /vendor/bin/modprobe -a -d /vendor/vendor_dlkm/lib/modules --all=/vendor/vendor_dlkm/lib/modules/modules.load#' "$TREE/etc/init/init.s5e3830.rc"
grep -q -- '--all=/vendor/vendor_dlkm/lib/modules/modules.load' "$TREE/etc/init/init.s5e3830.rc"

# A14 KeyMint TA links EVP_PKEY_get_raw_private_key, which A13 TEEGRIS lacks; cat keeps the inode label
ta=00000000-0000-0000-0000-4b45594d5354
cat "$A13V/tee/$ta" > "$TREE/tee/$ta"

# A13 Egis ET528: the A14 AIDL fingerprint HAL segfaults, the A13 32-bit HIDL fingerprint@3.0 HAL and its TA replace it
rm -f "$TREE/etc/vintf/manifest/vendor.samsung.hardware.biometrics.fingerprint-service.xml" \
      "$TREE/etc/init/vendor.samsung.hardware.biometrics.fingerprint-service.rc"
if a13hal hal_fingerprint_default_exec bin/hw/vendor.samsung.hardware.biometrics.fingerprint@3.0-service lib/hw/fingerprint.default.so; then
    a13 lib/hw/fingerprint.default.so 644 0 vendor_file
    a13 etc/init/vendor.samsung.hardware.biometrics.fingerprint@3.0-service.rc 644 0 vendor_configs_file
    a13 etc/vintf/manifest/vendor.samsung.hardware.biometrics.fingerprint@3.0-service.xml 644 0 vendor_configs_file
    ta=00000000-0000-0000-0000-46494e474552
    install -m 644 -o 0 -g 0 "$A13V/tee/$ta" "$TREE/tee/$ta"
    setfattr -n security.selinux -v "$(getfattr --only-values -n security.selinux "$TREE/tee/00000000-0000-0000-0000-46494e474502")" "$TREE/tee/$ta"
else
    echo "A13 fingerprint HAL skipped" >&2
fi

# A13 NFC is NXP PN557; the A14 Samsung S3NRN4V HAL is swapped for the A13 32-bit NXP AIDL HAL
if a13hal hal_nfc_default_exec bin/hw/android.hardware.nfc-service.nxp; then
    rm -f "$TREE/etc/init/sec-nfc-service.rc" "$TREE/etc/vintf/manifest/sec-nfc-service.xml"
    a13 etc/init/nfc-service-nxp.rc 644 0 vendor_configs_file
    a13 etc/vintf/manifest/nfc-service-nxp.xml 644 0 vendor_configs_file
    a13 etc/libnfc-nxp.conf 644 0 vendor_configs_file
    a13 etc/nfc/libnfc-nxp_RF.conf 644 0 vendor_configs_file
    a13 firmware/nfc/libpn557_fw.so 644 0 vendor_fw_file
else
    echo "A13 NFC HAL skipped" >&2
fi

# A13 camera stack: the setfile tuning struct is DDK specific (A13 ISV8PF blobs do not match the A14 ISV8RB DDK layout),
# so DDK, RTA and every setfile come from A13; the DDK/RTA are rebased from the 4.19 to the 5.10 LIB_START
for f in setfile_jn1.bin setfile_gc02m1.bin setfile_gc02m1_macro.bin setfile_gc08a3.bin setfile_gc5035.bin \
         tdnr_GC02M1.json tdnr_GC08A3.json tdnr_GC5035.json dual_cal_wide_sub.bin; do
    a13 "firmware/$f" 644 0 vendor_fw_file
done
for f in is_lib.bin is_rta.bin; do
    python3 "$KIT/ddk_rebase.py" "$A13V/firmware/$f" "$TREE/firmware/$f"
    chown 0:0 "$TREE/firmware/$f"; chmod 644 "$TREE/firmware/$f"
    label vendor_fw_file "$TREE/firmware/$f"
done
python3 "$KIT/camhal_patch.py" "$TREE/lib64/libexynoscamera3.so" "$WORK/libexynoscamera3.so"
cat "$WORK/libexynoscamera3.so" > "$TREE/lib64/libexynoscamera3.so"
install -m 644 -o 0 -g 0 "$A13V/etc/SetMultiCalInfo.bin" "$TREE/firmware/SetMultiCalInfo.bin"
label vendor_fw_file "$TREE/firmware/SetMultiCalInfo.bin"

# Same AW88230 amp and acf container as A14; the A13 file carries the A13 speaker tuning
a13 firmware/aw882xx_pid_2055b_acf.bin 644 0 vendor_fw_file

# Identity (build.prop, brand, FCC ID) stays A14; only hardware features come from A13
ff=$TREE/etc/floating_feature.xml
sed -i -e '/<SEC_FLOATING_FEATURE_LCD_CONFIG_HW_MDNIE>/d' "$ff"
for key in SEC_FLOATING_FEATURE_SENSOR_CONFIG_SABC_CAMERA_TYPE SEC_FLOATING_FEATURE_SENSOR_SUPPORT_SABC_LITE; do
    line=$(grep -m1 "<$key>" "$A13V/etc/floating_feature.xml")
    grep -q "<$key>" "$ff" || sed -i "s#^\(\s*\)</SecFloatingFeatureSet>#$line\n\1</SecFloatingFeatureSet>#" "$ff"
    grep -q "<$key>" "$ff"
done

rm -f "$OUT_IMG"
# stock A14 UUID so the same inputs give the same image hash
UUID=$(dump.erofs -s "$A14_IMG" | awk '/Filesystem UUID/ {print $NF}')
mkfs.erofs -zlz4hc,9 -T1230768000 -U "$UUID" -b4096 -Lvendor -E^xattr-name-filter --quiet "$OUT_IMG" "$TREE"
fsck.erofs "$OUT_IMG"
ls -l "$OUT_IMG"
sha1sum "$OUT_IMG"
