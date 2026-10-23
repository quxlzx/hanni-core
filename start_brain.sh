#!/bin/sh
cd "$(dirname "$0")"
echo "Starting HANNI from this repo... first run benches the models and"
echo "takes 2-3 minutes. Keep this terminal open while HANNI is running."
echo "(Need models first?  python3 scripts/get_models.py)"
echo
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
$PY scripts/firstboot.py --serve --wait --ui --port 8311
