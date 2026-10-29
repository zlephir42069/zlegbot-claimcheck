"""PASS when the path's mtime is strictly after the given timestamp."""

from __future__ import annotations

from datetime import datetime, timezone

from claimcheck.checks.files import claim_path
from claimcheck.errors import CheckError, ClaimFailed


def evaluate(options: dict, ctx) -> str:
    path = claim_path(ctx.root, options["path"])
    shown = options["path"]
    try:
        modified = path.stat().st_mtime
    except FileNotFoundError as exc:
        raise ClaimFailed(f"{shown} not found") from exc
    except OSError as exc:
        raise CheckError(f"could not stat file: {exc.__class__.__name__}") from exc
    after = options["after"]
    stamp = _fmt(modified)
    cutoff = _fmt(after)
    if modified <= after.timestamp():
        raise ClaimFailed(f"mtime {stamp} is not after {cutoff}")
    return f"mtime {stamp} is after {cutoff}"


def _fmt(value) -> str:
    if isinstance(value, datetime):
        when = value.astimezone(timezone.utc)
    else:
        when = datetime.fromtimestamp(value, timezone.utc)
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")
