#!/usr/bin/env python3
"""Assemble a portable HANNI stick (any directory or USB mount).

Layout produced:
  HANNI/
    soul/            SOUL.md + skills/ + memory.sqlite3 (the person)
    models/          MiniCPM5-2B, K2-Horizon-4B(3.7B), K2-Horizon-7B (Q4_K_M)
    binaries/        linux-x86_64 (portable) + linux-vulkan + README
    hanni-core/      source needed to run the native brain
    firstboot.py     runs on the HOST: probe -> micro-bench -> decide -> serve
    stick.json       manifest

Usage: make_stick.py --dest /media/you/HANNI [--skip-models] [--skip-source]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOME = Path.home()
MODELS = [("MiniCPM5-2B-Q4_K_M.gguf", "pocket"),
          ("K2-Horizon-4B-Q4_K_M.gguf", "small"),
          ("K2-Horizon-7B-Q4_K_M.gguf", "large")]
SOURCE_DIRS = ["src", "scripts", "config", "data", "pyproject.toml", "README.md"]


def copytree(src: Path, dst: Path) -> int:
    n = 0
    for p in src.rglob("*"):
        if p.is_dir() or "__pycache__" in p.parts or ".venv" in p.parts:
            continue
        target = dst / p.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
        n += 1
    return n


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", required=True)
    parser.add_argument("--skip-models", action="store_true")
    parser.add_argument("--skip-source", action="store_true")
    args = parser.parse_args()
    dest = Path(args.dest)
    (dest / "soul").mkdir(parents=True, exist_ok=True)

    # soul
    shutil.copy2(REPO / "data" / "SOUL.md", dest / "soul" / "SOUL.md")
    skills = REPO / "skills"
    if skills.is_dir():
        copytree(skills, dest / "soul" / "skills")
    mem = HOME / "hanni-hermes-bridge" / "state" / "memory.sqlite3"
    if mem.is_file():
        shutil.copy2(mem, dest / "soul" / "memory.sqlite3")

    # binaries
    bins = dest / "binaries"
    for name, build in (("linux-x86_64", "build-base2"), ("linux-vulkan", "build-vk3")):
        src = HOME / "llama-new" / build / "bin"
        if src.is_dir():
            dst = bins / name
            dst.mkdir(parents=True, exist_ok=True)
            for binary in ("llama-server", "llama-bench"):
                p = src / binary
                if p.is_file():
                    shutil.copy2(p, dst / binary)
            for so in src.glob("*.so*"):
                shutil.copy2(so, dst / so.name)
    (bins / "README.txt").write_text(
        "If both binaries SIGILL (ancient CPU), build on first use:\n"
        "  git clone https://github.com/ggml-org/llama.cpp && cmake -B build "
        "-DGGML_NATIVE=OFF && cmake --build build -j4 --target llama-server llama-bench\n")

    # models
    manifest_models = []
    if not args.skip_models:
        (dest / "models").mkdir(exist_ok=True)
        for fname, tier in MODELS:
            src = HOME / "models" / fname
            if src.is_file():
                dst = dest / "models" / fname
                if not (dst.is_file() and dst.stat().st_size == src.stat().st_size):
                    shutil.copy2(src, dst)
                manifest_models.append({"file": fname, "tier": tier, "bytes": src.stat().st_size})
            else:
                print(f"warning: model missing, skipped: {src}")

    # hanni-core source (native brain only needs these paths)
    if not args.skip_source:
        for item in SOURCE_DIRS:
            src = REPO / item
            if src.is_dir():
                copytree(src, dest / "hanni-core" / item)
            elif src.is_file():
                (dest / "hanni-core").mkdir(exist_ok=True)
                shutil.copy2(src, dest / "hanni-core" / item)

    shutil.copy2(REPO / "scripts" / "firstboot.py", dest / "firstboot.py")
    for wdir in ("wheels", "wheels-win"):
        src = REPO / wdir
        if src.is_dir():
            copytree(src, dest / wdir)
    (dest / "start_hanni.sh").write_text(
        '#!/bin/sh\ncd "$(dirname "$0")"\nexec python3 firstboot.py --serve "$@"\n')
    os.chmod(dest / "start_hanni.sh", 0o755)
    (dest / "START_HANNI.cmd").write_text(
        "@echo off\r\ncd /d %~dp0\r\npython firstboot.py --serve %*\r\n")
    (dest / "stick.json").write_text(json.dumps({
        "built": datetime.now(timezone.utc).isoformat(), "repo": str(REPO),
        "models": manifest_models,
        "sizes_mb": {p.parent.name + "/" + p.name: p.stat().st_size // (2**20)
                     for p in dest.rglob("*") if p.is_file() and p.stat().st_size > 2**20},
    }, indent=1))
    total = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
    print(f"stick ready at {dest}  ({total / 2**30:.1f} GiB)")


if __name__ == "__main__":
    main()
