"""PASS when a JSON path equals the expected value."""

from __future__ import annotations

import json
import math

from claimcheck.checks.files import claim_path, decode_text, read_text_bytes
from claimcheck.errors import CheckError, ClaimFailed
from claimcheck.jsonpath import Missing, resolve


def evaluate(options: dict, ctx) -> str:
    path = claim_path(ctx.root, options["path"])
    text = decode_text(read_text_bytes(path, options["path"]))
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CheckError(f"invalid JSON: {exc.msg}") from exc
    try:
        actual = resolve(document, options["compiled"])
    except Missing as exc:
        raise ClaimFailed(f"json path not found: {options['json_path']}") from exc
    expected = options["equals"]
    if not values_equal(actual, expected):
        raise ClaimFailed(f"got {_dump(actual)}; expected {_dump(expected)}")
    return f"got {_dump(actual)}"


def values_equal(actual, expected) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return isinstance(actual, bool) and isinstance(expected, bool) and actual is expected
    if _is_number(actual) and _is_number(expected):
        return actual == expected
    if isinstance(actual, str) or isinstance(expected, str):
        return actual == expected
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(
            values_equal(left, right) for left, right in zip(actual, expected)
        )
    if isinstance(actual, dict) and isinstance(expected, dict):
        if set(actual) != set(expected):
            return False
        return all(values_equal(actual[key], expected[key]) for key in actual)
    return actual == expected


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _dump(value) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        text = repr(value)
    if len(text) > 80:
        return text[:77] + "..."
    return text


def json_compatible(value) -> bool:
    """True when ``value`` can be compared with a json.loads result."""
    if value is None or isinstance(value, str) or isinstance(value, bool):
        return True
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(json_compatible(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and json_compatible(item) for key, item in value.items())
    return False
