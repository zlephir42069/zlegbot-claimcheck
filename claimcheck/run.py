"""Evaluate every claim. One failure does not stop the rest."""

from __future__ import annotations

import sys

from claimcheck.checks import evaluate
from claimcheck.config import AppConfig
from claimcheck.errors import CheckError, ClaimFailed
from claimcheck.report import ClaimResult, render_json, render_table


class Context:
    def __init__(self, config: AppConfig) -> None:
        self.root = config.root
        self.timeout = config.timeout
        self.redactor = config.redactor


def execute(config: AppConfig, *, as_json: bool) -> int:
    ctx = Context(config)
    results = [_one(claim, ctx) for claim in config.claims]
    text = render_json(results) if as_json else render_table(results)
    sys.stdout.write(text)
    if results and all(item.status == "PASS" for item in results):
        return 0
    return 1


def _one(claim, ctx: Context) -> ClaimResult:
    try:
        detail = evaluate(claim.type, claim.options, ctx)
        status = "PASS"
    except ClaimFailed as exc:
        status = "FAIL"
        detail = str(exc)
    except CheckError as exc:
        status = "ERROR"
        detail = str(exc)
    return ClaimResult(
        name=claim.name,
        type=claim.type,
        status=status,
        detail=_clean(ctx, detail),
    )


def _clean(ctx: Context, detail: str) -> str:
    text = " ".join(ctx.redactor.text(detail).split())
    if len(text) > 300:
        text = text[:297] + "..."
    return text or "no detail"
