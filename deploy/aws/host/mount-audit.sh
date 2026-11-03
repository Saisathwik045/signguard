#!/usr/bin/env bash
# Only the exact retained volume ID from the reviewed Terraform output may be mounted.
set -euo pipefail
volume_id="$1"
[[ "$volume_id" =~ ^vol-[0-9a-f]{8,32}$ ]]
device="/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${volume_id//-/}"
for attempt in {1..30}; do
  [[ -b "$device" ]] && break
  sleep 1
done
[[ -b "$device" ]]
fs_type=$(blkid -s TYPE -o value "$device" || true)
if [[ -z "$fs_type" ]]; then
  [[ -z "$(wipefs --noheadings --output TYPE -n "$device")" ]]
  mkfs.ext4 -m 0 "$device"
elif [[ "$fs_type" != ext4 ]]; then
  echo 'Refusing to reformat a pre-existing audit filesystem' >&2
  exit 1
fi
install -d -m 0770 -o 65532 -g 65532 /var/lib/signguard/audit
uuid=$(blkid -s UUID -o value "$device")
if ! grep -Fq "UUID=$uuid " /etc/fstab; then
  printf 'UUID=%s /var/lib/signguard/audit ext4 defaults,nodev,nosuid,noexec 0 2\n' "$uuid" >> /etc/fstab
fi
mountpoint -q /var/lib/signguard/audit || mount /var/lib/signguard/audit
chown 65532:65532 /var/lib/signguard/audit
chmod 0770 /var/lib/signguard/audit
