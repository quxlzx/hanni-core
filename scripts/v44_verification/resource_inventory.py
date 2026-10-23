"""Fresh read-only V4.4 inventory through original protected transports.

No model starts, raw remote requests, authentication changes, or process stops.
Private command lines and configuration remain only in ignored evidence storage.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from hanni.compute import ComputeRegistry
from hanni.compute.transport import InferenceTransport
from hanni.config.loader import load_config
from hanni.models.resource_manager import snapshot_resources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    assert out.is_relative_to((ROOT / "data/v44-verification").resolve()) and not out.exists()
    out.mkdir(parents=True)
    config = load_config(ROOT / "config", data_dir=out / "state", env={})
    spec = config.models.supervisor
    registry = ComputeRegistry(ROOT / "data")
    transport = InferenceTransport(registry)
    rows = []
    try:
        for worker in registry.workers():
            began = time.perf_counter()
            health = transport.health(worker)
            startup = worker.get("startup", {})
            row = {"endpoint_id": "worker:" + worker["worker_id"],
                   "configured_model": worker.get("model_id"),
                   "actual_health_status": health.get("status"),
                   "reported_model": health.get("model_id"),
                   "reported_context": health.get("context_reported"),
                   "configured_context": startup.get("context"),
                   "configured_backend": startup.get("kind"),
                   "configured_gpu": startup.get("gpu_device"),
                   "configured_concurrency": worker.get("concurrency", 1),
                   "resources": None,
                   "check_duration_ms": (time.perf_counter() - began) * 1000}
            if health.get("status") == "healthy":
                sample = transport.resources(worker)
                row["resources"] = {k: sample.get(k) for k in (
                    "ram_total_bytes", "ram_available_bytes", "vram_total_bytes",
                    "vram_free_bytes", "gpus", "resource_sampled_at")}
            rows.append(row)
            print(json.dumps({k: row[k] for k in (
                "endpoint_id", "actual_health_status", "reported_model", "check_duration_ms")}), flush=True)
        local_worker = {"worker_id": "local:supervisor", "node_id": "local",
                        "protocol": "llamacpp_openai", "local_url": spec.endpoint,
                        "model_id": spec.api_model}
        health = transport.health(local_worker)
        props = transport.request(local_worker, "GET", "/props") if health.get("status") == "healthy" else None
        port = __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(spec.endpoint).port
        listeners = [c.pid for c in psutil.net_connections(kind="tcp")
                     if c.status == psutil.CONN_LISTEN and c.laddr.port == port]
        provenance = []
        for pid in listeners:
            process = psutil.Process(pid)
            parent = process.parent()
            command = process.cmdline()
            provenance.append({"pid": pid, "create_time": process.create_time(),
                "process_name": process.name(), "command": command,
                "command_sha256": hashlib.sha256(json.dumps(command).encode()).hexdigest(),
                "parent_pid": parent.pid if parent else None,
                "parent_create_time": parent.create_time() if parent else None,
                "parent_command": parent.cmdline() if parent else None})
        private = {"sampled_at": time.time(), "local_configuration": asdict(spec),
                   "local_host": asdict(snapshot_resources()), "local_health": health,
                   "local_props": props, "local_provenance": provenance, "workers": rows,
                   "remote_starts": 0, "processes_stopped": 0,
                   "scope": "Fresh original registered protected transports only; no inference or service changes."}
        (out / "inventory.json").write_text(json.dumps(private, indent=2, default=str), encoding="utf8")
        print(json.dumps({"local_health": health.get("status"),
                          "reported_model": health.get("model_id"),
                          "local_listener_pids": listeners, "remote_starts": 0}), flush=True)
    finally:
        transport.close()
        registry.close()


if __name__ == "__main__":
    main()
