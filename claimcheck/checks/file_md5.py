"""PASS when the file's MD5 matches the expected hex digest."""

from __future__ import annotations

from claimcheck.checks.files import claim_path, file_md5
from claimcheck.errors import ClaimFailed


def evaluate(options: dict, ctx) -> str:
    path = claim_path(ctx.root, options["path"])
    got = file_md5(path, options["path"])
    expected = options["md5"]
    if got != expected:
        raise ClaimFailed(f"md5 {got} != expected {expected}")
    return f"md5 {got}"
