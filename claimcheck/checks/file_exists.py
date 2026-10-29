"""PASS when the path exists (a file or a directory)."""

from __future__ import annotations

from claimcheck.checks.files import claim_path
from claimcheck.errors import CheckError, ClaimFailed


def evaluate(options: dict, ctx) -> str:
    path = claim_path(ctx.root, options["path"])
    shown = options["path"]
    try:
        path.stat()
    except FileNotFoundError as exc:
        raise ClaimFailed(f"{shown} not found") from exc
    except OSError as exc:
        raise CheckError(f"could not stat path: {exc.__class__.__name__}") from exc
    kind = "directory" if path.is_dir() else "file"
    return f"{shown} {kind} exists"
