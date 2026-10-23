# Security Policy

## Supported versions

The project currently supports the latest main branch and the most recent release.

## Reporting a vulnerability

Please report suspected security issues privately by emailing the maintainer or using GitHub’s private security reporting feature if enabled for the repository.

Do not disclose details publicly until a fix is available.

## Local-first safety expectations

This project intentionally runs locally on the owner’s machine. It does not ship cloud-backed credentials or remote agent execution.

## Before sharing a repository or archive

Never commit `.env`, OAuth client downloads, Google tokens, model weights, `data/`, or raw evaluation results and checkpoints. The included `.gitignore`, source exporter, and distribution check exclude these paths. The public evaluation corpora are synthetic; `evals/real_world/` owner examples stay local.

Run `python scripts/check_distribution.py` after building a wheel and source archive. It reports file names and finding categories only, never matched secret values. Review staged files with `git diff --cached --name-only` before the first commit. If a credential was ever committed in a different copy of this repository, ignoring it now does not remove it from that copy’s history; rotate the credential before publishing.
