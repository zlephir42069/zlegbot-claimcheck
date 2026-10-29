"""JSON Pointer and a small dot path, used by json_path_equals.

A path that starts with ``/`` is a JSON Pointer (RFC 6901). ``$``, ``$.a.b``,
``a.b``, and ``items[0].name`` are the dot form. Digits in a dot segment index
a list and name an object key. Pointer tokens index a list only when every
character is a digit and there is no leading zero (``0`` itself is allowed).
"""

from __future__ import annotations

import re

_NAME = re.compile(r"[A-Za-z0-9_-]+")
_INDEX = re.compile(r"\[(\d+)\]")


class Missing(LookupError):
    """The path does not exist in this document."""


def compile_path(expr: str):
    """Return a compiled path. Raise ValueError when the syntax is wrong."""
    if not isinstance(expr, str):
        raise ValueError("json_path must be a string")
    text = expr.strip()
    if not text:
        raise ValueError("json_path must not be empty")
    if text.startswith("/"):
        return ("pointer", _pointer_parts(text))
    if text == "$":
        return ("whole", ())
    body = text
    if body.startswith("$."):
        body = body[2:]
    elif body.startswith("$["):
        body = body[1:]
    elif body.startswith("$"):
        raise ValueError("json_path must be a JSON Pointer, '$', or a dot path")
    if not body:
        raise ValueError("json_path must not be empty")
    return ("dot", tuple(_dot_tokens(body)))


def resolve(document, compiled):
    """Return the value at ``compiled`` or raise Missing."""
    kind, data = compiled
    if kind == "whole" or (kind == "pointer" and not data):
        return document
    current = document
    if kind == "pointer":
        for part in data:
            current = _pointer_step(current, part)
        return current
    for token_kind, value in data:
        current = _dot_step(current, token_kind, value)
    return current


def _pointer_parts(pointer: str) -> tuple:
    if pointer == "/":
        return ()
    raw = pointer.split("/")
    parts = []
    for part in raw[1:]:
        if re.search(r"~[^01]", part) or part.endswith("~"):
            raise ValueError(f"invalid JSON Pointer escape in {pointer!r}")
        parts.append(part.replace("~1", "/").replace("~0", "~"))
    return tuple(parts)


def _dot_tokens(body: str) -> list:
    tokens: list = []
    index = 0
    length = len(body)
    if body[0] == "[":
        index = _read_indexes(body, 0, tokens)
    else:
        index = _read_name(body, 0, tokens)
        index = _read_indexes(body, index, tokens)
    while index < length:
        if body[index] != ".":
            raise ValueError(f"invalid json_path {body!r}")
        index += 1
        if index >= length:
            raise ValueError(f"invalid json_path {body!r}")
        index = _read_name(body, index, tokens)
        index = _read_indexes(body, index, tokens)
    if not tokens:
        raise ValueError(f"invalid json_path {body!r}")
    return tokens


def _read_name(body: str, index: int, tokens: list) -> int:
    match = _NAME.match(body, index)
    if not match:
        raise ValueError(f"invalid json_path segment {body[index:]!r}")
    tokens.append(("key", match.group(0)))
    return match.end()


def _read_indexes(body: str, index: int, tokens: list) -> int:
    while index < len(body) and body[index] == "[":
        match = _INDEX.match(body, index)
        if not match:
            raise ValueError(f"invalid json_path index in {body!r}")
        tokens.append(("index", int(match.group(1))))
        index = match.end()
    return index


def _pointer_step(current, part: str):
    if isinstance(current, dict):
        if part not in current:
            raise Missing
        return current[part]
    if isinstance(current, list):
        index = _list_index(part)
        if index is None or index >= len(current):
            raise Missing
        return current[index]
    raise Missing


def _dot_step(current, token_kind: str, value):
    if token_kind == "index":
        if not isinstance(current, list) or value >= len(current):
            raise Missing
        return current[value]
    if isinstance(current, dict):
        if value not in current:
            raise Missing
        return current[value]
    if isinstance(current, list):
        index = _list_index(value)
        if index is None or index >= len(current):
            raise Missing
        return current[index]
    raise Missing


def _list_index(part: str):
    if not isinstance(part, str) or not part.isdigit():
        return None
    if part != "0" and part.startswith("0"):
        return None
    return int(part)
