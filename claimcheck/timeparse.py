"""Duration and timestamp parsing for timeouts and mtime_after."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_DURATION = re.compile(r"^(\d+(?:\.\d+)?)([smhdw])$")
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def parse_duration(value: str) -> timedelta:
    """Parse `30s`, `15m`, `12h`, `7d`, or `1w` into a timedelta."""
    text = value.strip().lower()
    match = _DURATION.fullmatch(text)
    if not match:
        raise ValueError(
            f"invalid duration {value!r} (use a number plus s, m, h, d, or w, such as 30s)"
        )
    amount = float(match.group(1))
    return timedelta(seconds=amount * _UNITS[match.group(2)])


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp. A trailing Z is UTC. Naive values are rejected."""
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"invalid timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp {value!r} needs a timezone offset")
    return parsed.astimezone(timezone.utc)
