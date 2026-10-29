"""CLI exit codes. 0 only when every claim passes. 2 is a bad file or bad usage."""

import json
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

import yaml

from conftest import REPO


def _env(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    for key in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        env.pop(key, None)
    return env


def _run(tmp_path, *args, stdin=None):
    return subprocess.run(
        [sys.executable, "-m", "claimcheck", *args],
        cwd=tmp_path,
        env=_env(tmp_path),
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def test_usage_validate_and_run(tmp_path):
    bare = _run(tmp_path)
    assert bare.returncode == 2

    missing = _run(tmp_path, "validate", "missing.yaml")
    assert missing.returncode == 2
    assert "claims file not found" in missing.stderr

    example = _run(tmp_path, "validate", str(REPO / "claims.example.yaml"))
    assert example.returncode == 0, example.stderr
    assert example.stdout.strip() == "ok"

    bad = tmp_path / "claims.yaml"
    bad.write_text("claims: []\n")
    invalid = _run(tmp_path, "validate", "claims.yaml")
    assert invalid.returncode == 2
    assert "config error:" in invalid.stderr

    note = tmp_path / "note.txt"
    note.write_text("hello\n")
    good = tmp_path / "good.yaml"
    good.write_text(
        """
claims:
  - name: note
    type: file_exists
    path: note.txt
  - name: greeting
    type: file_contains
    path: note.txt
    pattern: hello
"""
    )
    ran = _run(tmp_path, "run", "good.yaml")
    assert ran.returncode == 0, ran.stderr
    assert "PASS" in ran.stdout
    assert "2 claims: 2 passed, 0 failed, 0 errors" in ran.stdout

    bad_claim = tmp_path / "bad.yaml"
    bad_claim.write_text(
        """
claims:
  - name: note
    type: file_exists
    path: note.txt
  - name: gone
    type: file_exists
    path: missing.txt
"""
    )
    failed = _run(tmp_path, "run", "bad.yaml", "--json")
    assert failed.returncode == 1
    payload = json.loads(failed.stdout)
    assert payload["ok"] is False
    assert payload["summary"]["failed"] == 1
    assert "config error" not in failed.stderr


def test_root_flag_and_extract(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "note.txt").write_text("x")
    claims = tmp_path / "claims.yaml"
    claims.write_text(
        """
root: .
claims:
  - name: note
    type: file_exists
    path: note.txt
"""
    )
    wrong = _run(tmp_path, "run", "claims.yaml")
    assert wrong.returncode == 1
    right = _run(tmp_path, "run", "claims.yaml", "--root", "work")
    assert right.returncode == 0, right.stderr

    report = tmp_path / "report.txt"
    report.write_text("Created README.md\nmd5 of README.md is " + ("ab" * 16) + "\n")
    extracted = _run(tmp_path, "extract", "report.txt", "-o", "out.yaml")
    assert extracted.returncode == 0, extracted.stderr
    assert "wrote 2 claims" in extracted.stdout
    loaded = yaml.safe_load((tmp_path / "out.yaml").read_text(encoding="utf-8"))
    assert loaded["claims"][0]["type"] == "file_exists"
    assert loaded["claims"][1]["type"] == "file_md5"

    piped = _run(tmp_path, "extract", "-", stdin="generated `src/app.py`\n")
    assert piped.returncode == 0, piped.stderr
    assert "extracted 1 claim" in piped.stderr
    assert "src/app.py" in piped.stdout
    assert yaml.safe_load(piped.stdout)["claims"][0]["path"] == "src/app.py"

    missing_report = _run(tmp_path, "extract", "nope.txt")
    assert missing_report.returncode == 2
    assert "report not found" in missing_report.stderr


def test_console_script():
    candidates = [
        shutil.which("claimcheck"),
        str(Path(sysconfig.get_path("scripts")) / "claimcheck"),
        str(Path.home() / ".local" / "bin" / "claimcheck"),
    ]
    script = next((item for item in candidates if item and Path(item).is_file()), None)
    assert script is not None
    result = subprocess.run(
        [script, "validate", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "validate" in result.stdout
