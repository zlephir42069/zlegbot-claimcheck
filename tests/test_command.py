"""command_exit runs in root, hides stdout, and treats a timeout as ERROR."""

import sys

from claimcheck.config import load_config
from claimcheck.run import execute

_EXE = sys.executable


def test_exit_and_stdout_pattern(claims, tmp_path, capsys):
    path = claims(
        f"""
claims:
  - name: ok
    type: command_exit
    run: {_EXE} -c "print('hello')"
  - name: code
    type: command_exit
    run: {_EXE} -c "import sys; sys.exit(3)"
    exit: 0
  - name: text
    type: command_exit
    run: {_EXE} -c "print('hello')"
    stdout: goodbye
  - name: matched
    type: command_exit
    run: {_EXE} -c "print('hello')"
    stdout: '(?s)hello'
    exit: 0
"""
    )
    code = execute(load_config(path), as_json=False)
    out = capsys.readouterr().out
    assert code == 1
    assert "exit 0" in out
    assert "exit 3; expected 0" in out
    assert "stdout did not match" in out
    assert "stdout matched" in out
    assert "hello" not in out
    assert out.strip().splitlines()[-1] == "4 claims: 2 passed, 2 failed, 0 errors"


def test_timeout_is_error_and_root_must_be_a_directory(claims, tmp_path, capsys):
    path = claims(
        f"""
claims:
  - name: slow
    type: command_exit
    run: {_EXE} -c "import time; time.sleep(5)"
    timeout: 0.2
"""
    )
    code = execute(load_config(path), as_json=False)
    out = capsys.readouterr().out
    assert code == 1
    assert "ERROR" in out
    assert "timed out after 0.2s" in out

    target = tmp_path / "note.txt"
    target.write_text("x")
    path = claims(
        """
claims:
  - name: flag
    type: command_exit
    run: python -c "print('nope')"
"""
    )
    code = execute(load_config(path, root=str(target)), as_json=False)
    out = capsys.readouterr().out
    assert code == 1
    assert "root directory not found" in out
