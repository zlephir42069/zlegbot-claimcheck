"""json_path_equals compares decoded JSON, not text."""

import json

from claimcheck.config import load_config
from claimcheck.run import execute


def test_pointer_match_mismatch_and_parse_error(claims, tmp_path, capsys):
    document = {"version": "0.1.0", "n": 1, "items": [{"name": "note"}], "value": None}
    (tmp_path / "doc.json").write_text(json.dumps(document))
    (tmp_path / "nope.txt").write_text("not json")
    path = claims(
        """
claims:
  - name: version
    type: json_path_equals
    path: doc.json
    json_path: /version
    equals: "0.1.0"
  - name: number
    type: json_path_equals
    path: doc.json
    json_path: $.n
    equals: 1.0
  - name: item
    type: json_path_equals
    path: doc.json
    json_path: items[0].name
    equals: note
  - name: typed
    type: json_path_equals
    path: doc.json
    json_path: /n
    equals: "1"
  - name: missing
    type: json_path_equals
    path: doc.json
    json_path: /nope
    equals: 1
  - name: empty
    type: json_path_equals
    path: doc.json
    json_path: /value
    equals: null
  - name: whole
    type: json_path_equals
    path: doc.json
    json_path: /
    equals:
      version: "0.1.0"
      n: 1
      items:
        - name: note
      value: null
  - name: broken
    type: json_path_equals
    path: nope.txt
    json_path: /version
    equals: "0.1.0"
  - name: gone
    type: json_path_equals
    path: missing.json
    json_path: /version
    equals: "0.1.0"
"""
    )
    code = execute(load_config(path), as_json=False)
    out = capsys.readouterr().out
    assert code == 1
    assert "got \"0.1.0\"" in out
    assert "got 1" in out
    assert 'got "note"' in out or "got \"note\"" in out
    assert "expected \"1\"" in out
    assert "json path not found" in out
    assert "got null" in out
    assert "invalid JSON" in out
    assert "missing.json not found" in out
    assert out.strip().splitlines()[-1] == "9 claims: 5 passed, 3 failed, 1 error"
