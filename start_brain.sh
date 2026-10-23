#!/bin/sh
cd "$(dirname "$0")"
echo
echo " Choose HANNI's model:"
echo "   [a] Auto   - benchmark and pick the best this machine can host"
echo "   [2] 2B     - MiniCPM5-2B     (light, fast, small machines)"
echo "   [3] 3.7B   - K2 Horizon 3.7B (balanced)"
echo "   [4] 7B     - K2 Horizon 7B   (needs a real GPU or 16GB+ RAM)"
printf " Pick a/2/3/4 [a]: "
read TIER
case "$TIER" in
  2) TIER=2b ;;
  3) TIER=3.7b ;;
  4) TIER=7b ;;
  *) TIER=auto ;;
esac
echo
echo "Starting HANNI ($TIER tier)... first run benches the models and"
echo "takes 2-3 minutes. Keep this terminal open while HANNI is running."
echo "(Need models first?  python3 scripts/get_models.py)"
echo
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
$PY scripts/firstboot.py --serve --wait --ui --port 8311 --tier "$TIER"
echo
echo "HANNI stopped. You can close this terminal."
