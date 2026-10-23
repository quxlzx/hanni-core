#!/bin/sh
set -eu
bridge="$HOME/hanni-hermes-bridge"
test -f "$bridge/OWNER" && test "$(cat "$bridge/OWNER")" = 'hanni-hermes-v1'
systemctl --user disable --now hanni-hermes-bridge.service
echo 'Bridge disabled. Task receipts, tokens, and YAML backups retained for review.'
echo 'Restore a selected config.yaml.hanni-*.bak only after comparing unrelated changes.'
echo 'The existing hermes-gateway.service remains unchanged.'
