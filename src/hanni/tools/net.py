"""Read-only local network telemetry capabilities.

Everything here answers "is this machine online / how is its link behaving"
from measured local state. No capability in this module fetches remote content,
so screen/file/web text can never reach the network through it.
"""

from __future__ import annotations

import socket
import time
from typing import Any, Mapping

import psutil

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult
from hanni.tools.winshell import as_rows, quote, run_powershell, run_powershell_json

_PRIVATE_PREFIXES = ("10.", "192.168.", "172.16.", "172.17.", "172.18.", "172.19.",
                     "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
                     "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "169.254.")


def _adapters(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    include_down = bool(args.get("include_down", False))
    stats = psutil.net_if_stats()
    rows: list[dict[str, Any]] = []
    for name, addresses in psutil.net_if_addrs().items():
        stat = stats.get(name)
        up = bool(stat.isup) if stat else False
        if not up and not include_down:
            continue
        ipv4 = [a.address for a in addresses if a.family == socket.AF_INET]
        ipv6 = [a.address for a in addresses if a.family == socket.AF_INET6]
        rows.append({
            "name": name,
            "up": up,
            "speed_mbps": int(stat.speed) if stat else 0,
            "mtu": int(stat.mtu) if stat else 0,
            "ipv4": ipv4,
            "ipv6": ipv6,
            "private_only": all(any(a.startswith(p) for p in _PRIVATE_PREFIXES) for a in ipv4) if ipv4 else True,
        })
    rows.sort(key=lambda row: (not row["up"], row["name"]))
    primary = next((row for row in rows if row["up"] and row["ipv4"]), None)
    return ToolResult("net.info", True,
                      f"Found {len(rows)} network adapter(s)."
                      + (f" Primary local address {primary['ipv4'][0]} on {primary['name']}." if primary else ""),
                      {"adapters": rows, "primary_adapter": primary["name"] if primary else "",
                       "primary_ipv4": primary["ipv4"][0] if primary else "",
                       "online": None, "link_up": bool(primary), "internet_verified": False})


def _wifi(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    text = run_powershell("netsh wlan show interfaces", timeout=20, capability="net.wifi")
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip().casefold()] = value.strip()
    signal = fields.get("signal", "")
    percent = int(signal.rstrip("%")) if signal.rstrip("%").isdigit() else 0
    quality = "no wifi link" if not fields.get("ssid") else (
        "strong" if percent >= 70 else "usable" if percent >= 40 else "weak")
    return ToolResult("net.wifi", True,
                      f"Wi-Fi {fields.get('ssid', '(not connected)')}: signal {signal or 'unknown'} ({quality}).",
                      {"ssid": fields.get("ssid", ""), "state": fields.get("state", ""),
                       "signal_percent": percent, "quality": quality,
                       "radio_type": fields.get("radio type", ""), "band": fields.get("band", ""),
                       "channel": fields.get("channel", ""),
                       "receive_mbps": fields.get("receive rate (mbps)", ""),
                       "transmit_mbps": fields.get("transmit rate (mbps)", "")})


def _ping(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    host = str(args.get("host", "")).strip()
    count = max(1, min(int(args.get("count", 4)), 10))
    if not host or any(ch in host for ch in " \t\r\n|&;$<>()`'\"") or len(host) > 253:
        raise ValueError("host must be a single hostname or IP address")
    payload = run_powershell_json(
        f"Test-Connection -ComputerName {quote(host)} -Count {count} -ErrorAction SilentlyContinue "
        "| Select-Object -Property @{n='latency';e={if ($null -ne $_.Latency) { $_.Latency } else { $_.ResponseTime }}} | ConvertTo-Json -Compress",
        timeout=30, capability="net.ping")
    samples = [int(row.get("latency") or 0) for row in as_rows(payload)]
    received = len(samples)
    average = round(sum(samples) / received, 1) if received else 0.0
    ok = received > 0
    return ToolResult("net.ping", ok,
                      f"{host}: {received}/{count} replies"
                      + (f", average {average} ms." if ok else " - host unreachable."),
                      {"host": host, "sent": count, "received": received,
                       "loss_percent": round((count - received) / count * 100, 1),
                       "average_ms": average, "min_ms": min(samples) if samples else 0,
                       "max_ms": max(samples) if samples else 0})


def _dns_lookup(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    host = str(args.get("host", "")).strip()
    if not host or any(ch in host for ch in " \t\r\n|&;$<>()`'\"") or len(host) > 253:
        raise ValueError("host must be a single hostname")
    started = time.perf_counter()
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return ToolResult("net.dns_lookup", False, f"DNS lookup for {host} failed: {exc.strerror or exc}.",
                          {"host": host, "addresses": [], "resolved": False})
    elapsed = round((time.perf_counter() - started) * 1000, 1)
    addresses = sorted({info[4][0] for info in infos})
    return ToolResult("net.dns_lookup", True,
                      f"{host} resolves to {', '.join(addresses[:4])} in {elapsed} ms.",
                      {"host": host, "addresses": addresses, "resolved": True, "elapsed_ms": elapsed})


def _ports(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    limit = max(1, min(int(args.get("limit", 25)), 100))
    loopback_only = bool(args.get("loopback_only", False))
    rows: list[dict[str, Any]] = []
    for conn in psutil.net_connections(kind="inet"):
        if (conn.type != socket.SOCK_DGRAM and conn.status != psutil.CONN_LISTEN) or not conn.laddr:
            continue
        address = conn.laddr.ip
        if loopback_only and address not in {"127.0.0.1", "::1"}:
            continue
        name = ""
        if conn.pid:
            try:
                name = psutil.Process(conn.pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                name = ""
        rows.append({"address": address, "port": int(conn.laddr.port), "pid": conn.pid or 0,
                     "process": name, "loopback": address in {"127.0.0.1", "::1"}})
    rows.sort(key=lambda row: row["port"])
    return ToolResult("net.ports", True, f"{len(rows)} listening socket(s); showing up to {limit}.",
                      {"listeners": rows[:limit], "total": len(rows)})


def _throughput(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    seconds = max(1, min(int(args.get("seconds", 3)), 15))
    first = psutil.net_io_counters()
    time.sleep(seconds)
    second = psutil.net_io_counters()
    down = round((second.bytes_recv - first.bytes_recv) / seconds / 125_000, 2)
    up = round((second.bytes_sent - first.bytes_sent) / seconds / 125_000, 2)
    return ToolResult("net.throughput", True,
                      f"Over {seconds}s: about {down} Mbps down and {up} Mbps up on this machine.",
                      {"seconds": seconds, "download_mbps": down, "upload_mbps": up,
                       "bytes_received": second.bytes_recv - first.bytes_recv,
                       "bytes_sent": second.bytes_sent - first.bytes_sent,
                       "note": "observed local traffic, not a speed test"})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("net.info", "Read local network adapters, link state, and this machine's private IP addresses. Answers 'am I online' and 'what is my IP'.",
                       0, 0, {"include_down": bool},
                       {"adapters": "array", "primary_ipv4": "string", "online": "boolean|null"}, _adapters,
                       side_effect="read", tags=("network", "internet", "ip", "adapter", "ethernet", "online", "connection"),
                       aliases=("ip address", "am i online", "network status", "connected")),
        ToolDefinition("net.wifi", "Read the current Wi-Fi SSID, signal strength, band, and link rates.",
                       0, 0, {}, {"ssid": "string", "signal_percent": "integer", "quality": "string"}, _wifi,
                       side_effect="read", tags=("wifi", "wireless", "ssid", "signal", "network", "slow"),
                       aliases=("wifi signal", "wireless strength", "what network am i on")),
        ToolDefinition("net.ping", "Measure round-trip latency and packet loss to one host.",
                       1, 1, {"host": str, "count": int},
                       {"host": "string", "received": "integer", "average_ms": "number", "loss_percent": "number"}, _ping,
                       timeout_seconds=45, side_effect="external_action",
                       tags=("ping", "latency", "lag", "packet", "loss", "network", "reachable"),
                       aliases=("is it up", "how is my latency", "test connection")),
        ToolDefinition("net.dns_lookup", "Resolve a hostname to IP addresses and report resolution time.",
                       1, 1, {"host": str}, {"host": "string", "addresses": "array", "resolved": "boolean"}, _dns_lookup,
                       side_effect="external_action", tags=("dns", "resolve", "hostname", "lookup", "network"),
                       aliases=("dns problem", "cannot reach site")),
        ToolDefinition("net.ports", "List local listening TCP/UDP sockets and the processes holding them.",
                       0, 0, {"limit": int, "loopback_only": bool}, {"listeners": "array", "total": "integer"}, _ports,
                       side_effect="read", tags=("port", "listening", "socket", "server", "localhost", "loopback", "network"),
                       aliases=("what is running on port", "is the server up", "port in use")),
        ToolDefinition("net.throughput", "Sample actual bytes in/out on this machine over a few seconds to estimate current network throughput.",
                       0, 0, {"seconds": int}, {"download_mbps": "number", "upload_mbps": "number"}, _throughput,
                       timeout_seconds=30, side_effect="read",
                       tags=("bandwidth", "throughput", "speed", "network", "slow", "mbps", "transfer"),
                       aliases=("how fast is my internet right now", "network usage")),
    )
