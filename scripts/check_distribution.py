"""Fail a local or CI build if an archive contains private runtime material.

Only file names and finding categories are printed; matched values are never logged.
"""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile


BLOCKED_PARTS = {
    ".git", ".venv", "venv", "data", "checkpoints", "results",
    "inbox", "__pycache__", ".pytest-work", ".pytest-overnight",
}
BLOCKED_NAMES = {
    "credentials.json", "google-oauth-client.json", "token.json",
    "client_secret.json", "curated.jsonl",
}
TEXT_SUFFIXES = {".py", ".md", ".json", ".jsonl", ".yaml", ".yml", ".toml",
                 ".ps1", ".cmd", ".txt", ".csv", ".html", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".css", ".example"}
SECRET_PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "API credential": re.compile(rb"(?<![A-Za-z0-9_-])(?:AIza[A-Za-z0-9_-]{30,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[A-Za-z0-9-]{20,}|sk-[A-Za-z0-9_-]{32,})"),
    "OAuth token": re.compile(rb'"(?:refresh_token|access_token|client_secret)"\s*:\s*"(?!fixture-|test-|example-|your-|<)[^"\s]{20,}"', re.I),
    "personal email": re.compile(rb"(?<![A-Za-z0-9_.+-])[A-Za-z0-9_.+-]+@(?!(?:example\.(?:com|org|net|edu))\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.I),
    "local user path": re.compile(rb"(?:[A-Za-z]:[\\/]Users[\\/]|/home/|/Users/)(?!me\b|user\b|username\b|example\b)[A-Za-z0-9_.-]+", re.I),
}


def check_member(name: str, data: bytes) -> list[str]:
    parts = PurePosixPath(name.replace("\\", "/")).parts
    if not parts:
        return []
    lower = tuple(part.lower() for part in parts)
    base = lower[-1]
    issues = []
    if any(part in BLOCKED_PARTS for part in lower) or (len(lower) > 1 and lower[0].startswith("hanni-") and lower[1] == "models"):
        issues.append("private/runtime directory")
    if (base in BLOCKED_NAMES or base.startswith("client_secret") or
            base.startswith("google-oauth-client") or
            ("token" in base and base.endswith(".json")) or
            (any(word in base for word in ("secret", "credential", "api_key", "apikey")) and base.endswith(".json")) or
            base == ".env" or (base.startswith(".env.") and base != ".env.example") or
            base.endswith((".pem", ".key", ".p12", ".pfx", ".gguf", ".safetensors"))):
        issues.append("private/runtime filename")
    # The checker contains the literal detection expressions as source code.
    if base not in {"check_distribution.py","audit_public_release.py"} and PurePosixPath(base).suffix.lower() in TEXT_SUFFIXES:
        try:
            from audit_public_release import synthetic_email
        except ModuleNotFoundError:
            from scripts.audit_public_release import synthetic_email
        for kind, pattern in SECRET_PATTERNS.items():
            matches = list(pattern.finditer(data))
            if kind == "personal email":
                if any(label in name.lower() for label in ("license", "ofl.txt", "third_party_notices")):
                    continue
                matches = [match for match in matches if not synthetic_email(match.group())]
            if matches:
                issues.append(kind)
    return issues


def check_archive(path: Path) -> list[tuple[str, str]]:
    findings = []
    if path.suffix == ".whl" or path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                findings.extend((member.filename, issue) for issue in check_member(member.filename, archive.read(member)))
    elif path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                stream = archive.extractfile(member)
                if stream is not None:
                    findings.extend((member.name, issue) for issue in check_member(member.name, stream.read()))
    else:
        raise ValueError(f"Unsupported distribution: {path.name}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist"))
    args = parser.parse_args()
    archives = sorted((*args.directory.glob("*.whl"), *args.directory.glob("*.tar.gz")))
    if not archives:
        parser.error(f"No wheel or source archive found in {args.directory}")
    findings = []
    for path in archives:
        for member, category in check_archive(path):
            findings.append((path.name, member, category))
    for archive, member, category in findings:
        print(f"{archive}: {member}: {category}")
    if findings:
        print(f"FAIL: {len(findings)} release-safety finding(s)")
        return 1
    print(f"PASS: {len(archives)} distribution archive(s) contain no detected private material")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
