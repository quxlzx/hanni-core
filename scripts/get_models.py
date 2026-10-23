#!/usr/bin/env python3
"""Fetch the HANNI tier models and llama.cpp binaries into this repo.

Usage: python scripts/get_models.py [--tier 2b|3.7b|7b|all] [--root DIR]
Downloads land in <root>/models and <root>/binaries — exactly where
scripts/firstboot.py looks for them.
"""
import argparse
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

TIERS = {
    "2b": ("openbmb/MiniCPM5-2B-GGUF", "MiniCPM5-2B-Q4_K_M.gguf"),
    "3.7b": ("IFM/K2-Horizon-3.7B-GGUF", "K2-Horizon-4B-Q4_K_M.gguf"),
    "7b": ("IFM/K2-Horizon-7B-GGUF", "K2-Horizon-7B-Q4_K_M.gguf"),
}
BINARIES = {
    "posix": [("linux-x64", "linux-x86_64"), ("linux-vulkan-x64", "linux-vulkan")],
    "nt": [("win-cpu-x64", "windows-x86_64"), ("win-vulkan-x64", "windows-vulkan")],
}


def download(url: str, dest: Path) -> None:
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"already present: {dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"downloading {url.rsplit('/', 1)[-1]} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "hanni-core/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as out:
        got = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            got += len(chunk)
            if got % (32 << 20) < (1 << 20):
                print(f"  {got / 2**20:.0f} MiB", flush=True)
    tmp.rename(dest)
    print(f"done: {dest.name} ({dest.stat().st_size / 2**20:.0f} MiB)")


def latest_llama_release() -> tuple[str, list[dict]]:
    # llama.cpp's "latest" pointer is a stale v0.7.0 tag; the real builds are
    # the b#### tags. Walk the recent releases and take the newest one that
    # actually carries our platform's assets.
    req = urllib.request.Request(
        "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=15",
        headers={"User-Agent": "hanni-core/1.0", "Accept": "application/vnd.github+json"})
    wanted = BINARIES["nt" if sys.platform == "win32" else "posix"]
    for rel in json.loads(urllib.request.urlopen(req, timeout=30).read()):
        assets = rel.get("assets", [])
        if all(any(sub in a["name"] for a in assets) for sub, _ in wanted):
            return rel["tag_name"], assets
    raise SystemExit("no recent llama.cpp release carries this platform's binaries; "
                     "build from source (see README)")


def fetch_binaries(root: Path) -> None:
    tag, assets = latest_llama_release()
    print(f"llama.cpp release: {tag}")
    for asset_sub, dir_name in BINARIES["nt" if sys.platform == "win32" else "posix"]:
        target = root / "binaries" / dir_name
        if (target / ("llama-server" + (".exe" if sys.platform == "win32" else ""))).is_file():
            print(f"already present: {dir_name}")
            continue
        # find the exact asset name for this release
        match = next((a for a in assets if asset_sub in a["name"]), None)
        if not match:
            print(f"no '{asset_sub}' asset in {tag}; build from source (see README)")
            continue
        archive = root / "binaries" / match["name"]
        download(match["browser_download_url"], archive)
        target.mkdir(parents=True, exist_ok=True)
        if archive.suffix == ".zip":
            with zipfile.ZipFile(archive) as z:
                z.extractall(target)
        else:
            with tarfile.open(archive) as t:
                t.extractall(target)
        # flatten single-directory roots (llama-<ver>/...)
        subs = [p for p in target.iterdir() if p.is_dir()]
        if len(subs) == 1 and any((subs[0] / f).is_file() for f in ("llama-server", "llama-server.exe")):
            for f in subs[0].iterdir():
                shutil.move(str(f), target / f.name)
            subs[0].rmdir()
        archive.unlink(missing_ok=True)
        print(f"binaries ready: {dir_name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier", choices=[*TIERS, "all"], default="all")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--skip-binaries", action="store_true")
    args = parser.parse_args()
    root = args.root
    tiers = list(TIERS) if args.tier == "all" else [args.tier]
    for tier in tiers:
        repo, fname = TIERS[tier]
        download(f"https://huggingface.co/{repo}/resolve/main/{fname}",
                 root / "models" / fname)
    if not args.skip_binaries:
        if sys.platform == "win32":
            fetch_binaries(root)
        else:
            have = (root / "binaries" / "linux-x86_64" / "llama-server").is_file()
            if have:
                print("binaries already present: linux-x86_64")
            else:
                print("llama.cpp ships no official Linux binaries — build them with:\n"
                      "  ./scripts/build_llama.sh        (CPU; add VULKAN=1 for GPU)")
    print("\nnext: START_HANNI (or: python scripts/firstboot.py --serve --wait)")


if __name__ == "__main__":
    main()
