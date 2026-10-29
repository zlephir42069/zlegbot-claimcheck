"""PASS when a shell command exits with the expected code.

Optional ``stdout`` is a Python regular expression that must match stdout.
The claims file is trusted: the command runs through the shell, in ``root``.
Stdout is not printed. A timeout is ERROR, not FAIL.
"""

from __future__ import annotations

import re
import subprocess

from claimcheck.errors import CheckError, ClaimFailed


def evaluate(options: dict, ctx) -> str:
    timeout = options.get("timeout", ctx.timeout)
    if not ctx.root.is_dir():
        raise CheckError("root directory not found")
    try:
        completed = subprocess.run(
            options["run"],
            shell=True,
            cwd=ctx.root,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise CheckError(f"timed out after {timeout:g}s") from exc
    except OSError as exc:
        raise CheckError(f"could not run command: {exc.__class__.__name__}") from exc
    code = completed.returncode
    expected = options["exit"]
    if code != expected:
        raise ClaimFailed(f"exit {code}; expected {expected}")
    pattern = options.get("stdout")
    if pattern:
        try:
            matched = re.search(pattern, completed.stdout or "") is not None
        except re.error as exc:
            raise CheckError(f"invalid stdout pattern: {exc}") from exc
        if not matched:
            raise ClaimFailed(f"exit {code}; stdout did not match")
        return f"exit {code}; stdout matched"
    return f"exit {code}"
