"""A run keeps going after FAIL and ERROR. Secrets do not reach the table."""

import json

from claimcheck.config import load_config
from claimcheck.run import execute


def test_mixed_results_and_json(claims, tmp_path, capsys):
    (tmp_path / "note.txt").write_text("hello\n")
    (tmp_path / "dir").mkdir()
    path = claims(
        """
claims:
  - name: note
    type: file_exists
    path: note.txt
  - name: missing
    type: file_contains
    path: missing.txt
    pattern: hello
  - name: folder
    type: file_contains
    path: dir
    pattern: hello
"""
    )
    assert execute(load_config(path), as_json=True) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert [item["result"] for item in payload["claims"]] == ["PASS", "FAIL", "ERROR"]
    assert payload["summary"] == {"total": 3, "passed": 1, "failed": 1, "errors": 1}


def test_secret_in_a_path_is_redacted(claims, monkeypatch, capsys):
    monkeypatch.setenv("CLAIMCHECK_TOKEN", "SUPERSECRETTOKEN")
    path = claims(
        """
claims:
  - name: hidden
    type: file_exists
    path: ${CLAIMCHECK_TOKEN}
"""
    )
    assert execute(load_config(path), as_json=False) == 1
    out = capsys.readouterr().out
    assert "SUPERSECRETTOKEN" not in out
    assert "***" in out
    assert "FAIL" in out
