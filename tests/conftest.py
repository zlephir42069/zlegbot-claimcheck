"""Offline fixtures. Tests must not open a socket."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("tests must not open network connections")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
def claims(tmp_path):
    def write(text, name="claims.yaml"):
        path = tmp_path / name
        path.write_text(text)
        return path

    return write
