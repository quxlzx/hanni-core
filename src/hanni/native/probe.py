"""Boot-time tier selection for portable HANNI.

Two layers, per the measured fleet data (see hanni-portable-tiers notes):
1. probe()  - cheap hardware facts: RAM, cores, GPU names/VRAM (Vulkan via
   vulkaninfo when present, else lspci), disk free.
2. decide() - pure function mapping facts -> tier + model + server plan.
   A micro-benchmark result (measured tok/s from llama-bench) overrides the
   static guess when supplied, because spec-sheet inference is unreliable
   (thin clients measured 2 tok/s on models their class "should" handle).

Tiers (measured Oct 2026):
  full    - 78GB resident brain (Strata)      : >=64GB RAM and >=16GB VRAM
  large   - 8B class                         : >=10GB VRAM or >=16GB RAM
  small   - 3.7B class                       : >=8GB RAM
  pocket  - 2B class                         : >=5GB RAM
  none    - below pocket: use a remote brain over LAN/tailnet
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field


@dataclass
class Facts:
    ram_gb: float = 0.0
    cores: int = 0
    gpus: list = field(default_factory=list)   # [{'name':str,'vram_gb':float}]
    disk_free_gb: float = 0.0
    measured_decode_tps: float | None = None   # from llama-bench tg, if run


def probe(base_dir: str = ".") -> Facts:
    facts = Facts()
    try:
        with open("/proc/meminfo") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    facts.ram_gb = int(re.findall(r"\d+", line)[0]) / (1024 * 1024)
                    break
    except OSError:
        try:  # Windows fallback
            import psutil
            facts.ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        except Exception:
            pass
    try:
        import psutil
        facts.cores = psutil.cpu_count(logical=False) or 1
        facts.disk_free_gb = shutil.disk_usage(base_dir).free / (1024 ** 3)
    except Exception:
        pass

    if shutil.which("vulkaninfo"):
        try:
            out = subprocess.run(["vulkaninfo", "--summary"], capture_output=True, text=True, timeout=20).stdout
            name, vram = None, 0.0
            for line in out.splitlines():
                match = re.search(r"deviceName\s*=\s*(.+)", line)
                if match:
                    name = match.group(1).strip()
                match = re.search(r"globalMemorySize\s*=\s*(\d+)", line)
                if match and name:
                    facts.gpus.append({"name": name, "vram_gb": int(match.group(1)) / (1024 ** 3)})
                    name = None
        except Exception:
            pass
    if not facts.gpus and shutil.which("lspci"):
        try:
            out = subprocess.run(["lspci"], capture_output=True, text=True, timeout=10).stdout
            for line in out.splitlines():
                if re.search(r"VGA|3D controller|Display controller", line):
                    facts.gpus.append({"name": line.split(": ", 1)[-1][:80], "vram_gb": 0.0})
        except Exception:
            pass
    return facts


def decide(facts: Facts) -> dict:
    vram = max((gpu["vram_gb"] for gpu in facts.gpus), default=0.0)
    if facts.measured_decode_tps is not None:
        # measured truth beats spec-sheet guessing
        if facts.measured_decode_tps < 8:
            tier = "none"
        elif facts.measured_decode_tps < 15:
            tier = "pocket"
        elif facts.measured_decode_tps < 40:
            tier = "small"
        else:
            tier = "large" if vram < 16 else "large"
    elif facts.ram_gb >= 64 and vram >= 16:
        tier = "full"
    elif vram >= 8 or facts.ram_gb >= 16:
        # measured Oct 2026: 7B Q4 decodes 40 tok/s on 8GB (6600XT), 14 on 6GB
        # (Arc A380, floor), 5.8 on CPU (no) -> 7B needs >=8GB VRAM or a big-RAM
        # box running 3.7B comfortably instead
        tier = "large"
    elif facts.ram_gb >= 8:
        tier = "small"
    elif facts.ram_gb >= 5:
        tier = "pocket"
    else:
        tier = "none"
    models = {"full": "wonyoung-strata", "large": "k2-horizon-7b",
              "small": "k2-horizon-3.7b", "pocket": "minicpm5-2b", "none": None}
    return {"tier": tier, "model": models[tier], "facts": asdict(facts),
            "reason": f"ram={facts.ram_gb:.1f}GB vram={vram:.1f}GB cores={facts.cores} "
                      f"measured={facts.measured_decode_tps}"}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench-file", help="JSON {'decode_tps': N} from a llama-bench run")
    parser.add_argument("--base-dir", default=".")
    args = parser.parse_args()
    facts = probe(args.base_dir)
    if args.bench_file:
        try:
            facts.measured_decode_tps = float(json.loads(open(args.bench_file).read())["decode_tps"])
        except Exception:
            pass
    print(json.dumps(decide(facts), indent=1))


if __name__ == "__main__":
    main()
