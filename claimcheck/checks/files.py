"""Shared file reads for the path-based checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

from claimcheck.errors import CheckError, ClaimFailed

# Text, JSON, and line counts refuse larger files so a wrong path cannot
# pull a disk image into memory. file_md5 hashes in chunks and has no cap.
MAX_TEXT_BYTES = 20_000_000


def claim_path(root: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = root / path
    return path


def read_text_bytes(path: Path, shown: str) -> bytes:
    if path.is_dir():
        raise CheckError(f"{shown} is a directory")
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_TEXT_BYTES + 1)
    except FileNotFoundError as exc:
        raise ClaimFailed(f"{shown} not found") from exc
    except IsADirectoryError as exc:
        raise CheckError(f"{shown} is a directory") from exc
    except OSError as exc:
        raise CheckError(f"could not read file: {exc.__class__.__name__}") from exc
    if len(data) > MAX_TEXT_BYTES:
        raise CheckError(f"file exceeded {MAX_TEXT_BYTES} bytes")
    return data


def decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckError("file is not utf-8 text") from exc


def file_md5(path: Path, shown: str) -> str:
    if path.is_dir():
        raise CheckError(f"{shown} is a directory")
    digest = hashlib.md5(usedforsecurity=False)
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise ClaimFailed(f"{shown} not found") from exc
    except IsADirectoryError as exc:
        raise CheckError(f"{shown} is a directory") from exc
    except OSError as exc:
        raise CheckError(f"could not read file: {exc.__class__.__name__}") from exc
    return digest.hexdigest()
