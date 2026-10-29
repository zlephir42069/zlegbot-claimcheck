"""Check registry. Each evaluator returns a one-line detail, or raises."""

from __future__ import annotations

from claimcheck.checks import (
    command_exit,
    file_contains,
    file_exists,
    file_md5,
    json_path,
    line_count,
    mtime_after,
    url_status,
)

EVALUATORS = {
    "file_exists": file_exists.evaluate,
    "file_md5": file_md5.evaluate,
    "file_contains": file_contains.evaluate,
    "json_path_equals": json_path.evaluate,
    "line_count": line_count.evaluate,
    "url_status": url_status.evaluate,
    "command_exit": command_exit.evaluate,
    "mtime_after": mtime_after.evaluate,
}


def evaluate(claim_type: str, options: dict, ctx) -> str:
    try:
        evaluator = EVALUATORS[claim_type]
    except KeyError as exc:
        raise KeyError(f"unknown claim type {claim_type}") from exc
    return evaluator(options, ctx)
