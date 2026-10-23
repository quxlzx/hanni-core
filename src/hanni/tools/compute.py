"""Deterministic local computation: arithmetic, unit conversion, text and ids.

These exist so H.A.N.N.I. never asks a language model to do arithmetic, convert
units, or invent an identifier. Every result here is computed, reproducible, and
independent of the platform. ``calc.evaluate`` parses an expression with the
``ast`` module and walks a strict allow-list of nodes - it never calls ``eval``
and cannot reach a name, attribute, call, or import.
"""

from __future__ import annotations

import ast
import hashlib
import math
import operator
import random
import re
import secrets
import unicodedata
import uuid
from typing import Any, Mapping

from hanni.tools.base import ToolContext, ToolDefinition, ToolRequest, ToolResult

_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
           ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_MAX_EXPONENT = 64

# base unit per family; conversion is value * factor -> base -> / factor
_UNITS: dict[str, dict[str, float]] = {
    "length": {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0, "in": 0.0254, "inch": 0.0254,
               "inches": 0.0254, "ft": 0.3048, "foot": 0.3048, "feet": 0.3048, "yd": 0.9144,
               "yard": 0.9144, "mi": 1609.344, "mile": 1609.344, "miles": 1609.344},
    "mass": {"mg": 0.000001, "g": 0.001, "kg": 1.0, "oz": 0.028349523125, "lb": 0.45359237,
             "lbs": 0.45359237, "pound": 0.45359237, "pounds": 0.45359237, "st": 6.35029318},
    "data": {"b": 1.0, "byte": 1.0, "bytes": 1.0, "kb": 1024.0, "mb": 1024.0 ** 2,
             "gb": 1024.0 ** 3, "tb": 1024.0 ** 4, "bit": 0.125, "bits": 0.125,
             "kbit": 128.0, "mbit": 131072.0, "gbit": 134217728.0},
    "time": {"ms": 0.001, "s": 1.0, "sec": 1.0, "second": 1.0, "seconds": 1.0, "min": 60.0,
             "minute": 60.0, "minutes": 60.0, "h": 3600.0, "hr": 3600.0, "hour": 3600.0,
             "hours": 3600.0, "day": 86400.0, "days": 86400.0, "week": 604800.0, "weeks": 604800.0},
    "speed": {"mps": 1.0, "kph": 0.2777777778, "kmh": 0.2777777778, "mph": 0.44704, "knot": 0.514444},
}
_TEMPERATURE = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}
# Explicit spellings refer to existing factors; legacy KB/MB/GB/TB continue to
# use binary 1024 scaling. IEC spellings make that convention unambiguous.
_UNIT_ALIASES = {
    "millimeter": "mm", "millimeters": "mm", "millimetre": "mm", "millimetres": "mm",
    "centimeter": "cm", "centimeters": "cm", "centimetre": "cm", "centimetres": "cm",
    "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "kilometer": "km", "kilometers": "km", "kilometre": "km", "kilometres": "km",
    "yards": "yd", "milligram": "mg", "milligrams": "mg", "gram": "g", "grams": "g",
    "kilogram": "kg", "kilograms": "kg", "ounce": "oz", "ounces": "oz", "stone": "st", "stones": "st",
    "kilobyte": "kb", "kilobytes": "kb", "megabyte": "mb", "megabytes": "mb",
    "gigabyte": "gb", "gigabytes": "gb", "terabyte": "tb", "terabytes": "tb",
    "kib": "kb", "kibibyte": "kb", "kibibytes": "kb",
    "mib": "mb", "mebibyte": "mb", "mebibytes": "mb",
    "gib": "gb", "gibibyte": "gb", "gibibytes": "gb",
    "tib": "tb", "tebibyte": "tb", "tebibytes": "tb",
    "millisecond": "ms", "milliseconds": "ms", "knots": "knot",
}
_UNIT_VOCABULARY = ', '.join(sorted(_TEMPERATURE | set(_UNIT_ALIASES)
                                  | {unit for table in _UNITS.values() for unit in table}))
_UNIT_DESCRIPTION = ("Case-insensitive unit token; surrounding spaces are allowed. Supported: "
                     + _UNIT_VOCABULARY + ". KB/MB/GB/TB and their full names use legacy binary "
                     "1024 scaling, matching KiB/MiB/GiB/TiB. Bits remain distinct from bytes. "
                     "Source and target must belong to the same dimension.")


def _evaluate_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("only numeric literals are allowed")
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _evaluate_node(node.left), _evaluate_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ValueError(f"exponent is limited to +/-{_MAX_EXPONENT}")
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise ValueError("division by zero")
        return float(_BINARY[type(node.op)](left, right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return float(_UNARY[type(node.op)](_evaluate_node(node.operand)))
    raise ValueError("expression contains an unsupported element")


def evaluate_expression(expression: str) -> float:
    """Evaluate a plain arithmetic expression without eval()."""
    text = str(expression or "").strip()
    if not text:
        raise ValueError("expression is required")
    if len(text) > 200:
        raise ValueError("expression is limited to 200 characters")
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%\s*of\s+", r"(\1/100)*", text, flags=re.IGNORECASE)
    text = text.replace("x", "*") if re.fullmatch(r"[\d\s.x+\-*/()%^]+", text) else text
    text = text.replace("^", "**")
    if not re.fullmatch(r"[\d\s.+\-*/()%**]+", text.replace("**", "*")):
        raise ValueError("expression may contain only numbers and + - * / % ( ) ^")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"expression is not valid arithmetic: {exc.msg}") from exc
    value = _evaluate_node(tree)
    if not math.isfinite(value):
        raise ValueError("expression produced a non-finite result")
    return value


def _calc(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    expression = str(args.get("expression", ""))
    value = evaluate_expression(expression)
    rounded = round(value, int(args.get("decimals", 4)) if args.get("decimals") is not None else 4)
    pretty = f"{rounded:,.10g}"
    return ToolResult("calc.evaluate", True, f"{expression.strip()} = {pretty}",
                      {"expression": expression.strip(), "value": value, "rounded": rounded,
                       "formatted": pretty})


def _unit_family(unit: str) -> str | None:
    unit = unit.casefold()
    if unit in _TEMPERATURE:
        return "temperature"
    for family, table in _UNITS.items():
        if unit in table:
            return family
    return None


def _to_celsius(value: float, unit: str) -> float:
    unit = unit.casefold()
    if unit in {"c", "celsius"}:
        return value
    if unit in {"f", "fahrenheit"}:
        return (value - 32) * 5 / 9
    return value - 273.15


def _from_celsius(value: float, unit: str) -> float:
    unit = unit.casefold()
    if unit in {"c", "celsius"}:
        return value
    if unit in {"f", "fahrenheit"}:
        return value * 9 / 5 + 32
    return value + 273.15


def _convert(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    try:
        value = float(args.get("value"))
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be a number") from exc
    source = str(args.get("from_unit", "")).strip().casefold()
    target = str(args.get("to_unit", "")).strip().casefold()
    source_key = _UNIT_ALIASES.get(source, source)
    target_key = _UNIT_ALIASES.get(target, target)
    source_family, target_family = _unit_family(source_key), _unit_family(target_key)
    if source_family is None or target_family is None:
        raise ValueError(f"unknown unit; supported units are {_UNIT_VOCABULARY}")
    if source_family != target_family:
        raise ValueError(f"cannot convert {source_family} to {target_family}")
    if source_family == "temperature":
        converted = _from_celsius(_to_celsius(value, source), target)
    else:
        table = _UNITS[source_family]
        converted = value * table[source_key] / table[target_key]
    rounded = round(converted, 6)
    return ToolResult("unit.convert", True, f"{value:g} {source} = {rounded:g} {target}",
                      {"value": value, "from_unit": source, "to_unit": target,
                       "converted": converted, "rounded": rounded, "family": source_family})


def _text_stats(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    text = str(args.get("text", ""))
    if not text:
        raise ValueError("text is required")
    if len(text) > 200_000:
        raise ValueError("text is limited to 200000 characters")
    words = re.findall(r"[\w'-]+", text)
    sentences = [part for part in re.split(r"[.!?]+", text) if part.strip()]
    lines = text.splitlines() or [text]
    unique = {word.casefold() for word in words}
    minutes = round(len(words) / 200, 1)
    return ToolResult("text.stats", True,
                      f"{len(words)} words, {len(text)} characters, {len(sentences)} sentence(s), "
                      f"about {minutes} minute(s) to read aloud.",
                      {"characters": len(text), "characters_no_spaces": len(text.replace(" ", "")),
                       "words": len(words), "unique_words": len(unique), "lines": len(lines),
                       "sentences": len(sentences), "reading_minutes": minutes,
                       "longest_word": max(words, key=len) if words else ""})


def _hash_text(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    text = str(args.get("text", ""))
    algorithm = str(args.get("algorithm", "sha256")).casefold()
    if algorithm not in {"sha256", "sha1", "md5", "sha512"}:
        raise ValueError("algorithm must be sha256, sha512, sha1, or md5")
    if not text:
        raise ValueError("text is required")
    digest = hashlib.new(algorithm, text.encode("utf-8")).hexdigest()
    return ToolResult("text.hash", True, f"{algorithm} of {len(text)} character(s): {digest}",
                      {"algorithm": algorithm, "digest": digest, "length": len(text)})


def _normalize_text(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    text = str(args.get("text", ""))
    if not text:
        raise ValueError("text is required")
    mode = str(args.get("mode", "slug")).casefold()
    if mode not in {"slug", "upper", "lower", "title", "strip_accents", "collapse_spaces"}:
        raise ValueError("mode must be slug, upper, lower, title, strip_accents, or collapse_spaces")
    stripped = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    if mode == "slug":
        result = re.sub(r"[^a-z0-9]+", "-", stripped.casefold()).strip("-")
    elif mode == "strip_accents":
        result = stripped
    elif mode == "collapse_spaces":
        result = " ".join(text.split())
    else:
        result = getattr(text, mode)()
    return ToolResult("text.normalize", True, f"{mode}: {result[:200]}",
                      {"mode": mode, "result": result, "length": len(result)})


def _random_pick(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    options = args.get("options")
    count = max(1, min(int(args.get("count", 1)), 20))
    if isinstance(options, str):
        choices = [part.strip() for part in re.split(r"\s*(?:,| or )\s*", options) if part.strip()]
    elif isinstance(options, list):
        choices = [str(item).strip() for item in options if str(item).strip()]
    else:
        raise ValueError("options must be a list or a comma/or separated string")
    if len(choices) < 2:
        raise ValueError("provide at least two options")
    if count > len(choices):
        raise ValueError("count cannot exceed the number of options")
    generator = random.SystemRandom()
    picked = generator.sample(choices, count)
    return ToolResult("random.pick", True,
                      f"Picked {', '.join(picked)} from {len(choices)} option(s).",
                      {"options": choices, "picked": picked, "count": count})


def _random_number(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    low = int(args.get("minimum", 1))
    high = int(args.get("maximum", 100))
    if low >= high:
        raise ValueError("maximum must be greater than minimum")
    if high - low > 10 ** 9:
        raise ValueError("range is limited to one billion")
    value = random.SystemRandom().randint(low, high)
    return ToolResult("random.number", True, f"{value} (from {low}-{high} inclusive)",
                      {"value": value, "minimum": low, "maximum": high})


def _identifier(args: Mapping[str, Any], context: ToolContext, request: ToolRequest) -> ToolResult:
    kind = str(args.get("kind", "uuid4")).casefold()
    if kind not in {"uuid4", "hex", "urlsafe"}:
        raise ValueError("kind must be uuid4, hex, or urlsafe")
    length = max(8, min(int(args.get("length", 32)), 128))
    if kind == "uuid4":
        value = str(uuid.uuid4())
    elif kind == "hex":
        value = secrets.token_hex(length // 2)
    else:
        value = secrets.token_urlsafe(length)[:length]
    return ToolResult("id.generate", True, f"Generated a {kind} identifier: {value}",
                      {"kind": kind, "value": value,
                       "note": "not a credential; H.A.N.N.I. never stores generated secrets"})


def definitions() -> tuple[ToolDefinition, ...]:
    return (
        ToolDefinition("calc.evaluate", "Evaluate plain arithmetic (including 'X% of Y') deterministically, without asking a language model to do the maths.",
                       0, 0, {"expression": str, "decimals": int},
                       {"value": "number", "formatted": "string"}, _calc,
                       side_effect="read",
                       tags=("calculate", "math", "arithmetic", "percent", "sum", "multiply", "divide", "total"),
                       aliases=("what is", "how much is", "work out", "percent of", "add up")),
        ToolDefinition("unit.convert", "Convert between units of length, mass, data, time, speed, or temperature.",
                       0, 0, {"value": (int, float), "from_unit": str, "to_unit": str},
                       {"converted": "number", "family": "string"}, _convert,
                       side_effect="read",
                       tags=("convert", "unit", "miles", "kilometers", "pounds", "celsius", "fahrenheit",
                             "gigabytes", "temperature", "distance", "weight"),
                       aliases=("how many kilometers", "convert to", "in fahrenheit", "how many gb"),
                       argument_constraints={
                           "value": {"required": True, "nullable": False,
                                     "description": "Finite numeric value to convert."},
                           "from_unit": {"required": True, "nullable": False, "minLength": 1,
                                         "description": _UNIT_DESCRIPTION},
                           "to_unit": {"required": True, "nullable": False, "minLength": 1,
                                       "description": _UNIT_DESCRIPTION},
                       }),
        ToolDefinition("text.stats", "Count words, characters, sentences, and estimated reading time for a block of text.",
                       0, 0, {"text": str},
                       {"words": "integer", "characters": "integer", "reading_minutes": "number"}, _text_stats,
                       side_effect="read",
                       tags=("word", "count", "length", "characters", "reading", "text", "how long"),
                       aliases=("how many words", "word count", "how long is this")),
        ToolDefinition("text.hash", "Compute a sha256/sha512/sha1/md5 digest of a string, for comparing or fingerprinting content.",
                       0, 0, {"text": str, "algorithm": str}, {"digest": "string"}, _hash_text,
                       side_effect="read",
                       tags=("hash", "checksum", "sha256", "md5", "fingerprint", "digest", "verify"),
                       aliases=("hash this", "checksum of")),
        ToolDefinition("text.normalize", "Reshape a string: slug, upper, lower, title case, accent stripping, or whitespace collapse.",
                       0, 0, {"text": str, "mode": str}, {"result": "string"}, _normalize_text,
                       side_effect="read",
                       tags=("slug", "uppercase", "lowercase", "title", "case", "normalize", "filename", "text"),
                       aliases=("make a slug", "turn this into a filename", "uppercase this")),
        ToolDefinition("random.pick", "Choose fairly at random between options the owner supplies.",
                       0, 0, {"options": (str, list), "count": int},
                       {"picked": "array", "options": "array"}, _random_pick,
                       side_effect="read",
                       tags=("random", "pick", "choose", "decide", "coin", "flip", "shuffle", "between"),
                       aliases=("pick one", "choose for me", "flip a coin", "decide between")),
        ToolDefinition("random.number", "Generate a random whole number in a range.",
                       0, 0, {"minimum": int, "maximum": int}, {"value": "integer"}, _random_number,
                       side_effect="read",
                       tags=("random", "number", "dice", "roll", "between", "pick"),
                       aliases=("roll a dice", "random number between", "pick a number")),
        ToolDefinition("id.generate", "Generate a UUID or random hex/url-safe identifier.",
                       0, 0, {"kind": str, "length": int}, {"value": "string"}, _identifier,
                       side_effect="read",
                       tags=("uuid", "guid", "identifier", "id", "token", "generate", "random"),
                       aliases=("give me a uuid", "generate an id")),
    )
