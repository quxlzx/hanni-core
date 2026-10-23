#!/bin/sh
# Administrator prerequisite only. Does not stop/migrate Strata or change its
# settings. Docker-group access is administrative access to this machine.
set -eu
if [ "$(id -u)" -ne 0 ]; then
  echo 'Run this reviewed prerequisite script as administrator on Wonyoung.' >&2
  exit 1
fi
getent passwd wonyoung >/dev/null
if command -v docker >/dev/null 2>&1; then
  echo 'Docker already exists; inspect it instead of reinstalling.'
  exit 1
fi
apt-get install --no-install-recommends docker.io
usermod -aG docker wonyoung
systemctl enable --now docker
echo 'Reconnect the wonyoung SSH session, then verify Docker access and GPU isolation.'
echo 'Strata remains running natively until its separate validated cutover.'
