"""Secrets come from the environment only (optionally seeded from a local ``.env``).

V1 requires no secrets (docs/DECISIONS.md D-0010): ``SECRET_SPECS`` is empty and
``hanni health`` passes without a ``.env`` file. The machinery stays so that any
future, owner-approved secret is handled the same way (Master Spec §38):

* Values are wrapped in :class:`Secret`, whose ``str``/``repr`` never reveal them.
* Loaded values are registered with :mod:`hanni.logs.redaction` so they cannot
  leak through logs or reports.
* Error messages list secret *names*, never values.
* Real environment variables override ``.env`` entries; ``os.environ`` is never mutated.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from dotenv import dotenv_values

from hanni.logs.redaction import register_secret

_REDACTED = "<redacted>"


class Secret:
    """A secret value that does not print. Call :meth:`reveal` to use it."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError("Secret requires a non-empty string")
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"Secret({_REDACTED})"

    def __str__(self) -> str:
        return _REDACTED

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Secret):
            return hmac.compare_digest(self._value.encode("utf-8"), other._value.encode("utf-8"))
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]  # secrets are not hashable on purpose


def validate_min_length(minimum: int) -> Callable[[str], str | None]:
    """Validator factory for :class:`SecretSpec`."""
    return lambda value: None if len(value) >= minimum else f"must be at least {minimum} characters"


@dataclass(frozen=True, slots=True)
class SecretSpec:
    name: str
    description: str
    required: bool  # startup fails without it
    needed_from_milestone: int
    validate: Callable[[str], str | None]  # returns an error message, or None if valid


# V1 declares no secrets. Future ones are declared here and documented in .env.example.
SECRET_SPECS: tuple[SecretSpec, ...] = ()


class MissingSecretError(RuntimeError):
    def __init__(self, names: list[str]) -> None:
        self.names = tuple(names)
        super().__init__(f"missing required secret(s): {', '.join(names)} (see .env.example)")


class InvalidSecretError(RuntimeError):
    def __init__(self, problems: dict[str, str]) -> None:
        self.problems = dict(problems)
        detail = "; ".join(f"{name}: {message}" for name, message in problems.items())
        super().__init__(f"invalid secret(s): {detail}")


@dataclass(frozen=True, slots=True)
class Secrets:
    _values: Mapping[str, Secret]

    def get(self, name: str) -> Secret:
        return self._values[name]

    def has(self, name: str) -> bool:
        return name in self._values

    @property
    def present_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._values))

    def __repr__(self) -> str:
        return f"Secrets(present={self.present_names})"


def read_environment(env: Mapping[str, str] | None = None, dotenv_path: Path | None = None) -> dict[str, str]:
    """Merge a ``.env`` file (if present) under the real environment. Never mutates ``os.environ``."""
    merged: dict[str, str] = {}
    if dotenv_path is not None and dotenv_path.is_file():
        merged.update({k: v for k, v in dotenv_values(dotenv_path).items() if v is not None})
    merged.update(os.environ if env is None else env)
    return merged


def load_secrets(
    *,
    env: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
    specs: tuple[SecretSpec, ...] = SECRET_SPECS,
) -> Secrets:
    """Load, validate, and register every declared secret.

    Raises :class:`MissingSecretError` if a required secret is absent and
    :class:`InvalidSecretError` if a present secret fails validation.
    """
    source = read_environment(env, dotenv_path)
    values: dict[str, Secret] = {}
    missing: list[str] = []
    invalid: dict[str, str] = {}
    for spec in specs:
        raw = (source.get(spec.name) or "").strip()
        if not raw:
            if spec.required:
                missing.append(spec.name)
            continue
        problem = spec.validate(raw)
        if problem:
            invalid[spec.name] = problem
            continue
        values[spec.name] = Secret(raw)
        register_secret(spec.name, raw)
    if missing:
        raise MissingSecretError(missing)
    if invalid:
        raise InvalidSecretError(invalid)
    return Secrets(values)
