"""Load and validate a claims file. Secrets stay in the environment."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

from claimcheck.checks.json_path import json_compatible
from claimcheck.errors import ConfigError
from claimcheck.jsonpath import compile_path
from claimcheck.redact import Redactor, scrub
from claimcheck.timeparse import parse_duration, parse_iso

_ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_SENSITIVE_NAME = re.compile(
    r"(URL|URI|TOKEN|SECRET|PASSWORD|PASSWD|AUTH|WEBHOOK|HOOK)",
    re.IGNORECASE,
)
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_MD5 = re.compile(r"^[0-9a-fA-F]{32}$")

_TOP = {"root", "timeout", "claims"}
_COMMON = {"name", "type"}
_FIELDS = {
    "file_exists": _COMMON | {"path"},
    "file_md5": _COMMON | {"path", "md5"},
    "file_contains": _COMMON | {"path", "pattern"},
    "json_path_equals": _COMMON | {"path", "json_path", "equals"},
    "line_count": _COMMON | {"path", "min_rows", "skip_blank"},
    "url_status": _COMMON | {"url", "status", "timeout"},
    "command_exit": _COMMON | {"run", "exit", "stdout", "timeout"},
    "mtime_after": _COMMON | {"path", "after"},
}
# `min_rows` is accepted as an alias and stored as line_count.
_ALIASES = {"min_rows": "line_count"}

_MAX_TIMEOUT = 86400.0
_DEFAULT_TIMEOUT = 30.0


@dataclass
class Claim:
    name: str
    type: str
    options: dict


@dataclass
class AppConfig:
    path: Path
    root: Path
    timeout: float
    claims: list
    redactor: Redactor = field(repr=False)


def load_config(path: Path, root: str | None = None) -> AppConfig:
    """Load claims from YAML or JSON. ``root`` is the CLI override."""
    path = Path(path)
    data = _read_data(path)
    if isinstance(data, list):
        data = {"claims": data}
    if not isinstance(data, dict):
        raise ConfigError("claims file must be a mapping or a list")

    errors: list[str] = []
    redactor = Redactor()
    base = path.parent.resolve()

    for key in sorted(set(data) - _TOP):
        errors.append(f"unknown setting {key}")

    file_root = _resolve(base, _optional_path(data, "root", ".", errors, redactor))
    if root is not None:
        override = Path(root).expanduser()
        if not override.is_absolute():
            override = Path.cwd() / override
        file_root = override.resolve()
    timeout = _seconds(data.get("timeout", _DEFAULT_TIMEOUT), "timeout", errors, allow_zero=False)
    claims = _parse_claims(data.get("claims", None), errors, redactor)

    if errors:
        raise ConfigError(errors)
    if timeout is None:
        raise ConfigError("timeout is invalid")
    return AppConfig(
        path=path.resolve(),
        root=file_root,
        timeout=timeout,
        claims=claims,
        redactor=redactor,
    )


def _read_data(path: Path):
    if not path.is_file():
        raise ConfigError(f"claims file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigError("claims file is not utf-8 text") from exc
    except OSError as exc:
        raise ConfigError(f"could not read claims file: {exc.__class__.__name__}") from exc
    suffix = path.suffix.lower()
    stripped = text.lstrip()
    if suffix == ".json" or (suffix not in {".yaml", ".yml"} and stripped[:1] in "{["):
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(scrub(f"could not parse JSON: {exc.msg}")) from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(scrub(f"could not parse YAML: {exc}")) from exc


def _parse_claims(raw, errors: list[str], redactor: Redactor) -> list:
    if raw is None:
        errors.append("claims is required")
        return []
    if not isinstance(raw, list):
        errors.append("claims must be a list")
        return []
    if not raw:
        errors.append("claims must contain at least one claim")
        return []
    parsed = []
    seen = set()
    for index, body in enumerate(raw):
        label = f"claims[{index}]"
        if not isinstance(body, dict):
            errors.append(f"{label} must be a mapping")
            continue
        name = body.get("name")
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            errors.append(f"{label}.name must be a short letter-or-number identifier")
            label_name = label
        else:
            label_name = f"claim {name}"
            if name in seen:
                errors.append(f"duplicate claim name {name}")
            seen.add(name)
        claim_type = body.get("type")
        if claim_type in _ALIASES:
            claim_type = _ALIASES[claim_type]
        if claim_type not in _FIELDS:
            errors.append(f"{label_name}: unknown type {body.get('type')!r}")
            continue
        for key in sorted(set(body) - _FIELDS[claim_type]):
            errors.append(f"{label_name}: unknown setting {key}")
        options = _options(claim_type, body, label_name, errors, redactor)
        if not isinstance(name, str) or not _NAME.fullmatch(name) or options is None:
            continue
        parsed.append(Claim(name=name, type=claim_type, options=options))
    return parsed


def _options(claim_type, body, label, errors, redactor):
    if claim_type == "file_exists":
        path = _required_string(body, "path", label, errors, redactor, sensitive=False)
        if path is None:
            return None
        return {"path": path}
    if claim_type == "file_md5":
        path = _required_string(body, "path", label, errors, redactor, sensitive=False)
        digest = _required_string(body, "md5", label, errors, redactor, sensitive=False)
        if path is None or digest is None:
            return None
        if not _MD5.fullmatch(digest):
            errors.append(f"{label}.md5 must be 32 hex characters")
            return None
        return {"path": path, "md5": digest.lower()}
    if claim_type == "file_contains":
        path = _required_string(body, "path", label, errors, redactor, sensitive=False)
        pattern = _required_string(body, "pattern", label, errors, redactor, sensitive=False)
        if path is None or pattern is None:
            return None
        try:
            re.compile(pattern)
        except re.error as exc:
            errors.append(f"{label}.pattern is invalid: {exc}")
            return None
        return {"path": path, "pattern": pattern}
    if claim_type == "json_path_equals":
        return _json_options(body, label, errors, redactor)
    if claim_type == "line_count":
        path = _required_string(body, "path", label, errors, redactor, sensitive=False)
        if "min_rows" not in body:
            errors.append(f"{label}.min_rows is required")
            minimum = None
        else:
            minimum = _int(body.get("min_rows"), f"{label}.min_rows", errors, minimum=0)
        skip = _optional_bool(body, "skip_blank", False, f"{label}.skip_blank", errors)
        if path is None or minimum is None:
            return None
        return {"path": path, "min_rows": minimum, "skip_blank": skip}
    if claim_type == "url_status":
        url = _required_string(body, "url", label, errors, redactor, sensitive=True)
        if "status" not in body:
            errors.append(f"{label}.status is required")
            status = None
        else:
            status = _int(body.get("status"), f"{label}.status", errors, minimum=100)
            if status is not None and status > 599:
                errors.append(f"{label}.status must be an HTTP status code")
                status = None
        timeout_ok, timeout = _explicit_timeout(body, label, errors)
        if url is not None and not _require_http(url, f"{label}.url", errors):
            url = None
        if url is None or status is None or not timeout_ok:
            return None
        options = {"url": url, "status": status}
        if timeout is not None:
            options["timeout"] = timeout
        return options
    if claim_type == "command_exit":
        run = _required_string(body, "run", label, errors, redactor, sensitive=True)
        exit_ok = True
        exit_code = 0
        if "exit" in body:
            parsed = _int(body.get("exit"), f"{label}.exit", errors, minimum=None)
            if parsed is None:
                exit_ok = False
            else:
                exit_code = parsed
        stdout = None
        stdout_ok = True
        if "stdout" in body:
            stdout = _required_string(body, "stdout", label, errors, redactor, sensitive=False)
            if stdout is None:
                stdout_ok = False
            else:
                try:
                    re.compile(stdout)
                except re.error as exc:
                    errors.append(f"{label}.stdout is invalid: {exc}")
                    stdout_ok = False
        timeout_ok, timeout = _explicit_timeout(body, label, errors)
        if run is None or not exit_ok or not stdout_ok or not timeout_ok:
            return None
        options = {"run": run, "exit": exit_code}
        if timeout is not None:
            options["timeout"] = timeout
        if stdout is not None:
            options["stdout"] = stdout
        return options
    if claim_type == "mtime_after":
        path = _required_string(body, "path", label, errors, redactor, sensitive=False)
        if "after" not in body:
            errors.append(f"{label}.after is required")
            after = None
        else:
            after = _timestamp(body.get("after"), f"{label}.after", errors, redactor)
        if path is None or after is None:
            return None
        return {"path": path, "after": after}
    return None


def _json_options(body, label, errors, redactor):
    path = _required_string(body, "path", label, errors, redactor, sensitive=False)
    expr = _required_string(body, "json_path", label, errors, redactor, sensitive=False)
    expected_ok = True
    expected = None
    if "equals" not in body:
        errors.append(f"{label}.equals is required")
        expected_ok = False
    else:
        expected = body.get("equals")
        if isinstance(expected, str):
            before = len(errors)
            expected = _expand(
                expected,
                sensitive=False,
                redactor=redactor,
                errors=errors,
                label=f"{label}.equals",
            )
            if len(errors) > before:
                expected_ok = False
        if isinstance(expected, datetime):
            errors.append(f"{label}.equals must be quoted if it is a timestamp")
            expected_ok = False
        elif not json_compatible(expected):
            errors.append(f"{label}.equals must be a JSON value")
            expected_ok = False
    compiled = None
    if expr is not None:
        try:
            compiled = compile_path(expr)
        except ValueError as exc:
            errors.append(f"{label}.json_path: {exc}")
    if path is None or compiled is None or not expected_ok:
        return None
    return {"path": path, "json_path": expr, "compiled": compiled, "equals": expected}


def _required_string(body, key, label, errors, redactor, *, sensitive: bool):
    if key not in body:
        errors.append(f"{label}.{key} is required")
        return None
    value = body.get(key)
    before = len(errors)
    expanded = _expand(
        value,
        sensitive=sensitive,
        redactor=redactor,
        errors=errors,
        label=f"{label}.{key}",
    )
    if not isinstance(value, str) or len(errors) > before:
        return None
    if not expanded.strip():
        errors.append(f"{label}.{key} must not be empty")
        return None
    return expanded


def _optional_bool(body, key, default, label, errors) -> bool:
    if key not in body:
        return default
    value = body.get(key)
    if not isinstance(value, bool):
        errors.append(f"{label} must be true or false")
        return default
    return value


def _optional_path(data, key, default, errors, redactor) -> str:
    if key not in data:
        return default
    value = data.get(key)
    before = len(errors)
    expanded = _expand(value, sensitive=False, redactor=redactor, errors=errors, label=key)
    if not isinstance(value, str) or len(errors) > before:
        return default
    if not expanded.strip():
        errors.append(f"{key} must be a path")
        return default
    return expanded


def _explicit_timeout(body, label, errors):
    """Return ``(ok, seconds)``. ``seconds`` is None when the key is absent.

    Absent means the claim inherits the file-level timeout. An invalid value
    is not ok, and the claim is dropped after the error is recorded.
    """
    if "timeout" not in body:
        return True, None
    parsed = _seconds(body.get("timeout"), f"{label}.timeout", errors, allow_zero=False)
    if parsed is None:
        return False, None
    return True, parsed


def _expand(value, *, sensitive: bool, redactor: Redactor, errors: list[str], label: str) -> str:
    if not isinstance(value, str):
        errors.append(f"{label} must be a string")
        return ""
    missing = []
    # `$${` is an escaped `${` so a shell command can keep a literal variable.
    sentinel = "\x00CLAIMCHECK_DOLLAR\x00"
    protected = value.replace("$${", sentinel)

    def repl(match):
        name = match.group(1)
        if name not in os.environ:
            missing.append(name)
            return match.group(0)
        env_value = os.environ[name]
        if sensitive or _SENSITIVE_NAME.search(name):
            redactor.add(env_value)
        return env_value

    expanded = _ENV.sub(repl, protected).replace(sentinel, "${")
    for name in sorted(set(missing)):
        errors.append(f"{label} references unset environment variable {name}")
    if missing:
        return expanded
    if sensitive and expanded != value and "://" in expanded:
        redactor.add(expanded)
    return expanded


def _require_http(url: str, label: str, errors: list[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append(f"{label} must be an http(s) URL")
        return False
    return True


def _seconds(value, label, errors, *, allow_zero: bool):
    if isinstance(value, bool):
        errors.append(f"{label} must be seconds or a duration")
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
    elif isinstance(value, str):
        try:
            seconds = parse_duration(value).total_seconds()
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            return None
    else:
        errors.append(f"{label} must be seconds or a duration")
        return None
    if seconds < 0 or seconds > _MAX_TIMEOUT or (not allow_zero and seconds <= 0):
        if allow_zero:
            errors.append(f"{label} must be between 0 and {_MAX_TIMEOUT:g} seconds")
        else:
            errors.append(f"{label} must be greater than 0 and at most {_MAX_TIMEOUT:g} seconds")
        return None
    return seconds


def _int(value, label, errors, *, minimum):
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{label} must be an integer")
        return None
    if minimum is not None and value < minimum:
        errors.append(f"{label} must be >= {minimum}")
        return None
    return value


def _timestamp(value, label, errors, redactor):
    if isinstance(value, str):
        before = len(errors)
        value = _expand(value, sensitive=False, redactor=redactor, errors=errors, label=label)
        if len(errors) > before:
            return None
        text = value.strip()
        if not text:
            errors.append(f"{label} must be a quoted ISO-8601 timestamp")
            return None
    elif isinstance(value, datetime):
        text = value.isoformat()
    else:
        errors.append(f"{label} must be a quoted ISO-8601 timestamp")
        return None
    try:
        return parse_iso(text)
    except ValueError as exc:
        errors.append(f"{label}: {exc}")
        return None


def _resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()
