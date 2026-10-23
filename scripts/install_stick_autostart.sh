#!/usr/bin/env bash
# Optional: auto-run the HANNI stick when it is plugged into THIS Linux box.
# Matches USB drives whose filesystem label starts with "HANNI".
# Usage: sudo HANNI_USER=<youruser> bash scripts/install_stick_autostart.sh
set -euo pipefail
HANNI_USER="${HANNI_USER:?set HANNI_USER=<user to run HANNI as>}"

cat > /etc/udev/rules.d/99-hanni-stick.rules <<'RULE'
ACTION=="add", SUBSYSTEM=="block", ENV{ID_FS_LABEL}=="HANNI*", TAG+="systemd", ENV{SYSTEMD_WANTS}+="hanni-stick@k$(basename %k).service"
RULE

cat > /etc/systemd/system/hanni-stick@.service <<UNIT
[Unit]
Description=HANNI stick firstboot on %i
BindsTo=dev-%i.device
After=dev-%i.device

[Service]
Type=oneshot
RemainAfterExit=yes
User=${HANNI_USER}
Environment=DISPLAY=:0
ExecStartPre=/bin/mkdir -p /run/hanni-stick
ExecStartPre=/bin/mount -o uid=${HANNI_USER},gid=$(id -gn ${HANNI_USER}) /dev/%i /run/hanni-stick
ExecStart=/bin/sh -c 'cd /run/hanni-stick && python3 firstboot.py --serve'
ExecStop=/bin/umount /run/hanni-stick
UNIT

systemctl daemon-reload
echo "installed. Label your stick HANNI (e.g. fatlabel /dev/sdX1 HANNI) and it auto-boots on plug-in."
