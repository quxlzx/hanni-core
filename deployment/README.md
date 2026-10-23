# Native automation stack (no Hermes)

1. `~/.config/hanni/brain.env` (chmod 600): HANNI_MODEL_API_KEY + HANNI_MODEL_CONFIG
2. copy these two units into ~/.config/systemd/user/, `systemctl --user daemon-reload`
3. `systemctl --user enable --now hanni-native-bridge hanni-cron`
4. add jobs: `python -m hanni.native.cron --root ~/hanni-cron/state add --prompt ... --interval 1800 --auto-approve local_terminal`
5. copy your memory.sqlite3 into the root so the cron brain remembers.
Bridge: :8097 (token in root/bridge.token). Verified live Oct 20: fleet-ping job
runs every 30 min, 4 receipts, review_required with report.
