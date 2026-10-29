"""Claims-file validation, env substitution, and the example file."""

from datetime import datetime, timezone

import pytest

from claimcheck.config import load_config
from claimcheck.errors import ConfigError

from conftest import REPO


def test_example_covers_every_type():
    config = load_config(REPO / "claims.example.yaml")
    assert {claim.type for claim in config.claims} == {
        "file_exists",
        "file_md5",
        "file_contains",
        "json_path_equals",
        "line_count",
        "url_status",
        "command_exit",
        "mtime_after",
    }
    assert config.claims[4].options["min_rows"] == 2
    assert config.claims[4].options["skip_blank"] is True
    assert config.timeout == 30
    assert config.root == (REPO / "claims.example.yaml").parent.resolve()


def test_json_file_top_level_list_and_alias(claims, tmp_path):
    path = claims(
        """
[
  {"name": "note", "type": "file_exists", "path": "note.txt"},
  {"name": "rows", "type": "min_rows", "path": "note.txt", "min_rows": 1}
]
""",
        name="claims.json",
    )
    config = load_config(path)
    assert [claim.type for claim in config.claims] == ["file_exists", "line_count"]
    assert config.claims[1].options["min_rows"] == 1
    assert config.root == tmp_path.resolve()


def test_relative_root_timeout_and_dollar_escape(claims, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAIMCHECK_TOKEN", "SUPERSECRETTOKEN")
    monkeypatch.setenv("HOME", "/home/tester")
    path = claims(
        """
root: work
timeout: 15s
claims:
  - name: hook
    type: url_status
    url: https://example.com/hook/${CLAIMCHECK_TOKEN}
    status: 200
  - name: flag
    type: command_exit
    run: echo $${CLAIMCHECK_TOKEN}
    timeout: 4
"""
    )
    config = load_config(path)
    assert config.root == (tmp_path / "work").resolve()
    assert config.timeout == 15
    assert config.claims[0].options["url"].endswith("/SUPERSECRETTOKEN")
    assert "timeout" not in config.claims[0].options
    assert config.claims[1].options["run"] == "echo ${CLAIMCHECK_TOKEN}"
    assert config.claims[1].options["exit"] == 0
    assert config.claims[1].options["timeout"] == 4
    assert "SUPERSECRETTOKEN" not in config.redactor.text(config.claims[0].options["url"])
    assert config.redactor.text("SUPERSECRETTOKEN") == "***"
    # The escaped command did not register the token by itself; the URL did.
    assert "SUPERSECRETTOKEN" not in config.redactor.text("prefix SUPERSECRETTOKEN")


def test_cli_root_overrides_file_root(claims, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = claims(
        """
root: from-file
claims:
  - name: note
    type: file_exists
    path: note.txt
"""
    )
    other = tmp_path / "elsewhere"
    config = load_config(path, root="elsewhere")
    assert config.root == other.resolve()


def test_equals_null_and_quoted_timestamp(claims):
    path = claims(
        """
claims:
  - name: empty
    type: json_path_equals
    path: doc.json
    json_path: /value
    equals: null
  - name: fresh
    type: mtime_after
    path: doc.json
    after: "2026-10-29T00:00:00Z"
"""
    )
    config = load_config(path)
    assert config.claims[0].options["equals"] is None
    assert config.claims[1].options["after"] == datetime(2026, 10, 29, tzinfo=timezone.utc)


def test_collects_independent_errors(claims):
    path = claims(
        """
root: 1
timeout: 0
claims:
  - name: note
    type: file_exists
  - name: note
    type: no_such
    path: a
  - name: hash
    type: file_md5
    path: a
    md5: abc
    extra: 1
  - name: body
    type: file_contains
    path: a
    pattern: '['
  - name: doc
    type: json_path_equals
    path: a
    json_path: '..'
  - name: rows
    type: line_count
    path: a
    min_rows: -1
    skip_blank: nope
  - name: health
    type: url_status
    url: file:///tmp/x
    status: 99
  - name: flag
    type: command_exit
    run: ""
    stdout: '['
    timeout: nope
  - name: Bad Name
    type: mtime_after
    path: a
    after: "yesterday"
  - name: fresh
    type: mtime_after
    path: a
"""
    )
    with pytest.raises(ConfigError) as caught:
        load_config(path)
    text = "\n".join(caught.value.messages)
    assert "root must be a string" in text
    assert "timeout must be greater than 0" in text
    assert "claim note.path is required" in text
    assert "duplicate claim name note" in text
    assert "unknown type 'no_such'" in text
    assert "md5 must be 32 hex" in text
    assert "unknown setting extra" in text
    assert "pattern is invalid" in text
    assert "json_path" in text
    assert "equals is required" in text
    assert "min_rows must be >= 0" in text
    assert "skip_blank must be true or false" in text
    assert "must be an http(s) URL" in text
    assert "status must be >= 100" in text
    assert "run must not be empty" in text
    assert "stdout is invalid" in text
    assert "invalid duration" in text
    assert "name must be a short" in text
    assert "yesterday" in text
    assert "claim fresh.after is required" in text


def test_rejects_unset_env_and_naive_timestamp(claims, monkeypatch):
    monkeypatch.delenv("CLAIMCHECK_URL", raising=False)
    path = claims(
        """
claims:
  - name: health
    type: url_status
    url: ${CLAIMCHECK_URL}
    status: 200
  - name: fresh
    type: mtime_after
    path: a
    after: "2026-10-29T00:00:00"
"""
    )
    with pytest.raises(ConfigError) as caught:
        load_config(path)
    text = "\n".join(caught.value.messages)
    assert "unset environment variable CLAIMCHECK_URL" in text
    assert "needs a timezone offset" in text


def test_missing_file_and_empty_claims(claims, tmp_path):
    with pytest.raises(ConfigError) as caught:
        load_config(tmp_path / "missing.yaml")
    assert "not found" in caught.value.messages[0]
    path = claims("claims: []\n")
    with pytest.raises(ConfigError) as caught:
        load_config(path)
    assert "at least one claim" in "\n".join(caught.value.messages)
