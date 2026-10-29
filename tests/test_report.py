"""Text table and JSON summary count claims, nothing else."""

import json

from claimcheck.report import ClaimResult, render_json, render_table


def test_table_aligns_and_counts():
    results = [
        ClaimResult("readme", "file_exists", "PASS", "README.md file exists"),
        ClaimResult("hash", "file_md5", "FAIL", "md5 abc != expected def"),
        ClaimResult("health", "url_status", "ERROR", "timed out after 10s"),
    ]
    text = render_table(results)
    lines = text.splitlines()
    assert lines[0].split() == ["name", "type", "result", "detail"]
    assert "PASS" in text
    assert "FAIL" in text
    assert "ERROR" in text
    assert lines[-1] == "3 claims: 1 passed, 1 failed, 1 error"
    assert text.endswith("\n")


def test_json_ok_only_when_every_claim_passes():
    results = [ClaimResult("readme", "file_exists", "PASS", "README.md file exists")]
    payload = json.loads(render_json(results))
    assert payload["ok"] is True
    assert payload["summary"] == {"total": 1, "passed": 1, "failed": 0, "errors": 0}
    assert payload["claims"][0]["result"] == "PASS"

    mixed = results + [ClaimResult("hash", "file_md5", "FAIL", "mismatch")]
    assert json.loads(render_json(mixed))["ok"] is False
