"""PASS when a GET returns the expected HTTP status. Redirects are not followed."""

from __future__ import annotations

from claimcheck.errors import ClaimFailed
from claimcheck.http import fetch_status


def evaluate(options: dict, ctx) -> str:
    timeout = options.get("timeout", ctx.timeout)
    code = fetch_status(options["url"], timeout)
    expected = options["status"]
    if code != expected:
        raise ClaimFailed(f"HTTP {code}; expected {expected}")
    return f"HTTP {code}"
