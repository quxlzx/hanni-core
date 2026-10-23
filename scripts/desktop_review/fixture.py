"""Isolated review fixture; synthetic readings/actions, no assistant or SSH."""
from __future__ import annotations

import json
import math
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from hanni.config.loader import load_config
from hanni.dashboard.chat import ChatHub
from hanni.dashboard.cluster import ClusterMonitor
from hanni.dashboard.server import DashboardServer, Handler

ROOT = Path(__file__).resolve().parents[2]


class ReviewFixture:
    def __enter__(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="hanni-independent-review-")
        self.config = load_config(ROOT / "config", data_dir=Path(self.temporary.name), env={})
        self.hub = ChatHub()
        self.hub.ready = True
        self.shutdown = threading.Event()
        self.writes = []
        self.operations = {}
        model = self.config.models.supervisor
        self.sample = {
            "sampled_at": time.time(), "model_status": "ready", "error": None,
            "model": {"file": model.model_file, "quantization": model.quantization,
                      "context": model.context_length},
            "model_residency": {model.id: {"model": model.model_file, "role": model.role,
                "state": "READY", "pinned": True, "resident": True, "active_inferences": 0,
                "process_ram_mb": 2480, "device": "review-gpu", "context": model.context_length}},
            "activity": {"input_level": .06, "speaking": False, "microphone_active": True},
            "interaction": {"response_in_progress": False, "tts_speaking": False,
                            "voice_engaged": False, "active_background_jobs": 0},
            "safe_mode": False, "uptime_seconds": 27300, "battery": None,
            "disk": {"percent": 42.8, "used_gb": 438, "total_gb": 1024},
            "network": {"receive_bps": 40960, "send_bps": 10240},
            "resources": {"cpu_percent": 12.4, "ram_percent": 38.2,
                "ram_used_gb": 12.2, "ram_total_gb": 32,
                "gpus": [{"name": "Review GPU (synthetic)", "memory_used_mb": 3072,
                          "memory_total_mb": 8192, "utilization_percent": None,
                          "temperature_c": None}], "gpu_note": "Estimated memory"},
        }
        self.gpu = {"mode": "auto", "devices": [{"id": "review-gpu", "name": "Review GPU (synthetic)",
            "total_mb": 8192, "auto_eligible": True}], "selected_device_name": "Review GPU (synthetic)",
            "selected_device_id": "review-gpu", "current_device_id": "review-gpu", "restart_required": False}
        self.audio = {"input_id": "default", "output_id": "default",
            "inputs": [{"id": "1", "name": "Review microphone (synthetic)", "hostapi": "WASAPI"}],
            "outputs": [{"id": "review-speaker", "name": "Review speaker (synthetic)"}],
            "input_error": None, "output_error": None}
        def probe(node, peer):
            index = ["hanni", "wonyoung", "haerin", "chaewon", "minju", "wonhee", "jeongyeon", "karina"].index(node.id)
            ready = node.id not in {"haerin", "wonyoung"}
            now = time.time()
            cpu = 12.5 + index * 5 + math.sin(now / 4) * 4
            return {"status": "offline" if node.id == "haerin" else "online",
                "checked_at": now, "sampled_at": now if ready else None,
                "metrics": {"cpu_percent": cpu, "ram_percent": 35. + index * 4,
                    "ram_used_bytes": (5.6 + index * .64) * 1024**3,
                    "ram_total_bytes": 16 * 1024**3} if ready else None,
                "address": node.tailscale_ip, "connection": "tailscale",
                "availability_source": "telemetry" if ready else "tailscale",
                "message": None if ready else "SSH host key needs verification." if node.id == "wonyoung" else "Node is unreachable.",
                "uptime_seconds": 90123 + index * 48200 if ready else None,
                "hostname": node.id, "os": "Linux", "tailscale_ssh_enabled": True,
                "processes": [{"name": "llama-server" if index == 0 else "python3",
                               "cpu_percent": 125. if index == 0 else cpu,
                               "ram_percent": 30.}] if ready else None}
        self.monitor = ClusterMonitor(probe=probe, tailnet=lambda: {"state": "connected", "peers": {}})
        for _ in range(12):
            self.monitor.sample_once()
        def cluster_snapshot():
            self.monitor.sample_once()
            return self.monitor.snapshot()
        cluster = SimpleNamespace(start=lambda: None, close=lambda: None, snapshot=cluster_snapshot)
        def project_power(snapshot):
            for node in snapshot["nodes"]:
                enabled = node["metrics"] is not None
                node["power"] = {"actions": {a: {"enabled": enabled,
                    "reason": None if enabled else "Power controls unavailable."} for a in ["sleep", "reboot"]},
                    "last_operation": self.operations.get(node["id"])}
            return snapshot
        def execute_power(data):
            self.writes.append({"kind": "power", **data})
            operation = {**data, "requested_at": time.time(), "status": "accepted",
                         "message": "Synthetic review request accepted. No remote command executed."}
            self.operations[data["node"]] = operation
            return operation
        power = SimpleNamespace(start=lambda: None, close=lambda: None, project=project_power, execute=execute_power)
        def project_terminal(snapshot):
            for node in snapshot["nodes"]:
                node["terminal"] = {"enabled": not node["maintenance"],
                    "reason": "Under repair" if node["maintenance"] else None}
            return snapshot
        def execute_terminal(data):
            self.writes.append({"kind": "terminal", **data})
            return {**data, "opened": True, "message": "Synthetic terminal request. No terminal opened."}
        terminal = SimpleNamespace(project=project_terminal, execute=execute_terminal)
        fixture = self
        class ReviewHandler(Handler):
            def do_GET(self):
                route = self.path.split("?", 1)[0]
                if route in {"/api/audio-devices", "/api/gpu-routing"}:
                    if not self._allowed(): return
                    return self._send(200, json.dumps(fixture.audio if route.endswith("audio-devices") else fixture.gpu).encode())
                return super().do_GET()
            def do_POST(self):
                route = self.path.split("?", 1)[0]
                if route in {"/api/audio-devices", "/api/gpu-routing"}:
                    if not self._allowed(write=True): return
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 20000: return self._send(400, b'{"error":"Invalid request"}')
                    data = json.loads(self.rfile.read(size))
                    fixture.writes.append({"kind": route, **data})
                    state = fixture.audio if route.endswith("audio-devices") else fixture.gpu
                    state.update(data)
                    return self._send(200, json.dumps(state).encode())
                return super().do_POST()
        self.server = DashboardServer(0, SimpleNamespace(config=self.config,
            snapshot=lambda: {**self.sample, "sampled_at": time.time()}), self.hub,
            shutdown_event=self.shutdown, cluster=cluster, cluster_power=power, cluster_terminal=terminal)
        self.server.RequestHandlerClass = ReviewHandler
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.hub.close()
        self.hub.db.close()
        self.temporary.cleanup()
