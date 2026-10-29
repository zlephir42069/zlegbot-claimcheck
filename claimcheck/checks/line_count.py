"""PASS when the file has at least min_rows lines."""

from __future__ import annotations

from claimcheck.checks.files import claim_path, decode_text, read_text_bytes
from claimcheck.errors import ClaimFailed


def evaluate(options: dict, ctx) -> str:
    path = claim_path(ctx.root, options["path"])
    text = decode_text(read_text_bytes(path, options["path"]))
    lines = text.splitlines()
    if options.get("skip_blank"):
        lines = [line for line in lines if line.strip()]
    count = len(lines)
    minimum = options["min_rows"]
    if count < minimum:
        raise ClaimFailed(f"{count} lines; min_rows {minimum}")
    return f"{count} lines >= min_rows {minimum}"
