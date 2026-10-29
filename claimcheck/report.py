"""Render PASS, FAIL, and ERROR rows. Every count is a number of claims."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class ClaimResult:
    name: str
    type: str
    status: str
    detail: str


def render_table(results: list[ClaimResult]) -> str:
    headers = ("name", "type", "result", "detail")
    rows = [(item.name, item.type, item.status, item.detail) for item in results]
    widths = [len(cell) for cell in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    def format_row(row) -> str:
        padded = [cell.ljust(widths[index]) for index, cell in enumerate(row)]
        return "  ".join(padded).rstrip()

    passed, failed, errors = _counts(results)
    lines = [format_row(headers), format_row(tuple("-" * width for width in widths))]
    lines.extend(format_row(row) for row in rows)
    lines.append("")
    lines.append(
        f"{_noun(len(results), 'claim', 'claims')}: "
        f"{passed} passed, {failed} failed, {_noun(errors, 'error', 'errors')}"
    )
    lines.append("")
    return "\n".join(lines)


def render_json(results: list[ClaimResult]) -> str:
    passed, failed, errors = _counts(results)
    payload = {
        "ok": bool(results) and failed == 0 and errors == 0,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "errors": errors,
        },
        "claims": [
            {
                "name": item.name,
                "type": item.type,
                "result": item.status,
                "detail": item.detail,
            }
            for item in results
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _noun(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count == 1 else plural}"


def _counts(results: list[ClaimResult]) -> tuple[int, int, int]:
    passed = sum(1 for item in results if item.status == "PASS")
    failed = sum(1 for item in results if item.status == "FAIL")
    errors = sum(1 for item in results if item.status == "ERROR")
    return passed, failed, errors
