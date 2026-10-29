"""PASS when a Python regular expression matches the file text."""

from __future__ import annotations

import re

from claimcheck.checks.files import claim_path, decode_text, read_text_bytes
from claimcheck.errors import CheckError, ClaimFailed


def evaluate(options: dict, ctx) -> str:
    path = claim_path(ctx.root, options["path"])
    text = decode_text(read_text_bytes(path, options["path"]))
    try:
        matched = re.search(options["pattern"], text) is not None
    except re.error as exc:
        raise CheckError(f"invalid pattern: {exc}") from exc
    if not matched:
        raise ClaimFailed("pattern not found")
    return "pattern matched"
