"""file_exists, file_md5, file_contains, line_count, and mtime_after."""

import os
from datetime import datetime, timezone

from claimcheck.config import load_config
from claimcheck.run import execute


def _run(claims, text, capsys):
    path = claims(text)
    code = execute(load_config(path), as_json=False)
    out = capsys.readouterr().out
    return code, out


def test_line_and_hash_result_counts(claims, tmp_path, capsys):
    (tmp_path / "note.txt").write_text("hello\n\nworld\n")
    (tmp_path / "empty.txt").write_bytes(b"")
    (tmp_path / "dir").mkdir()
    digest = "d41d8cd98f00b204e9800998ecf8427e"
    code, out = _run(
        claims,
        f"""
claims:
  - name: note
    type: file_exists
    path: note.txt
  - name: folder
    type: file_exists
    path: dir
  - name: missing
    type: file_exists
    path: nope.txt
  - name: hash
    type: file_md5
    path: empty.txt
    md5: {digest.upper()}
  - name: bad_hash
    type: file_md5
    path: note.txt
    md5: {digest}
  - name: greeting
    type: file_contains
    path: note.txt
    pattern: '(?s)hello.+world'
  - name: absent_text
    type: file_contains
    path: note.txt
    pattern: goodbye
  - name: rows
    type: line_count
    path: note.txt
    min_rows: 3
  - name: blanks
    type: line_count
    path: note.txt
    min_rows: 3
    skip_blank: true
  - name: dir_hash
    type: file_md5
    path: dir
    md5: {digest}
""",
        capsys,
    )
    assert code == 1
    assert "note.txt file exists" in out
    assert "dir directory exists" in out
    assert "nope.txt not found" in out
    assert f"md5 {digest}" in out
    assert "!= expected" in out
    assert "pattern matched" in out
    assert "pattern not found" in out
    assert "3 lines >= min_rows 3" in out
    assert "2 lines; min_rows 3" in out
    assert "dir is a directory" in out
    # exists note PASS, folder PASS, missing FAIL,
    # hash PASS, bad_hash FAIL, greeting PASS, absent FAIL,
    # rows PASS, blanks FAIL, dir_hash ERROR
    assert out.strip().splitlines()[-1] == "10 claims: 5 passed, 4 failed, 1 error"


def test_mtime_is_strictly_after(claims, tmp_path, capsys):
    note = tmp_path / "note.txt"
    note.write_text("x")
    stamp = 1_700_000_000
    os.utime(note, (stamp, stamp))
    after = datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    later = datetime.fromtimestamp(stamp + 5, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    code, out = _run(
        claims,
        f"""
claims:
  - name: same
    type: mtime_after
    path: note.txt
    after: "{after}"
  - name: older
    type: mtime_after
    path: note.txt
    after: "{later}"
  - name: gone
    type: mtime_after
    path: missing.txt
    after: "{after}"
""",
        capsys,
    )
    assert code == 1
    assert "is not after" in out
    assert "missing.txt not found" in out
    os.utime(note, (stamp + 5, stamp + 5))
    code, out = _run(
        claims,
        f"""
claims:
  - name: newer
    type: mtime_after
    path: note.txt
    after: "{after}"
""",
        capsys,
    )
    assert code == 0
    assert "is after" in out
    assert "1 passed, 0 failed, 0 errors" in out


def test_absolute_path_ignores_root_and_large_text_is_an_error(claims, tmp_path, monkeypatch, capsys):
    outside = tmp_path / "outside.txt"
    outside.write_text("hi\n")
    big = tmp_path / "big.txt"
    big.write_text("hello\n")
    nested = tmp_path / "nested"
    nested.mkdir()
    monkeypatch.setattr("claimcheck.checks.files.MAX_TEXT_BYTES", 4)
    code, out = _run(
        claims,
        f"""
root: nested
claims:
  - name: abs
    type: file_contains
    path: {outside}
    pattern: hi
  - name: big
    type: line_count
    path: {big}
    min_rows: 1
""",
        capsys,
    )
    assert code == 1
    assert "pattern matched" in out
    assert "exceeded 4 bytes" in out


def test_binary_file_is_an_error(claims, tmp_path, capsys):
    (tmp_path / "blob.bin").write_bytes(b"\xff\xfe")
    code, out = _run(
        claims,
        """
claims:
  - name: blob
    type: file_contains
    path: blob.bin
    pattern: a
""",
        capsys,
    )
    assert code == 1
    assert "ERROR" in out
    assert "not utf-8" in out
