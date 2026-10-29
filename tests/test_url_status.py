"""url_status uses the HTTP code and does not follow redirects. No sockets."""

import urllib.error

import pytest

from claimcheck.config import load_config
from claimcheck.errors import CheckError
from claimcheck.http import _NoRedirect, fetch_status
from claimcheck.run import execute


class _Response:
    def __init__(self, status):
        self.status = status

    def read(self, size=-1):
        return b""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Body:
    def close(self):
        return None

    def read(self, size=-1):
        return b""


def test_fetch_status_maps_success_http_error_and_network(monkeypatch):
    seen = {}

    def opener(request, timeout):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["agent"] = request.get_header("User-agent")
        return _Response(200)

    monkeypatch.setattr("claimcheck.http._open", opener)
    assert fetch_status("https://example.com/health", 5) == 200
    assert seen["timeout"] == 5
    assert seen["agent"].startswith("claimcheck/")

    def missing(request, timeout):
        raise urllib.error.HTTPError(
            "https://example.com/health", 404, "missing", {}, _Body()
        )

    monkeypatch.setattr("claimcheck.http._open", missing)
    assert fetch_status("https://example.com/health", 5) == 404

    def down(request, timeout):
        raise urllib.error.URLError("name resolution failed")

    monkeypatch.setattr("claimcheck.http._open", down)
    with pytest.raises(CheckError) as caught:
        fetch_status("https://example.com/health", 5)
    assert "fetch failed" in str(caught.value)

    def slow(request, timeout):
        raise urllib.error.URLError(TimeoutError("slow"))

    monkeypatch.setattr("claimcheck.http._open", slow)
    with pytest.raises(CheckError) as caught:
        fetch_status("https://example.com/health", 3)
    assert "timed out after 3s" in str(caught.value)


def test_redirect_handler_keeps_the_first_status():
    handler = _NoRedirect()
    with pytest.raises(urllib.error.HTTPError) as caught:
        handler.redirect_request(
            urllib.request.Request("https://example.com/old"),
            _Body(),
            302,
            "found",
            {},
            "https://example.com/new",
        )
    assert caught.value.code == 302


def test_claim_compares_status_and_redacts_webhook_errors(claims, monkeypatch, capsys):
    def fake(url, timeout):
        if url.endswith("/slow"):
            raise CheckError(
                "fetch failed: https://hooks.slack.com/services/T000/B000/SECRETVALUE"
            )
        if url.endswith("/missing"):
            return 404
        if url.endswith("/old"):
            return 302
        return 200

    monkeypatch.setattr("claimcheck.checks.url_status.fetch_status", fake)
    path = claims(
        """
timeout: 12
claims:
  - name: health
    type: url_status
    url: https://example.com/health
    status: 200
  - name: missing
    type: url_status
    url: https://example.com/missing
    status: 200
  - name: moved
    type: url_status
    url: https://example.com/old
    status: 302
  - name: slow
    type: url_status
    url: https://example.com/slow
    status: 200
"""
    )
    code = execute(load_config(path), as_json=False)
    out = capsys.readouterr().out
    assert code == 1
    assert "HTTP 200" in out
    assert "HTTP 302" in out
    assert "HTTP 404; expected 200" in out
    assert "SECRETVALUE" not in out
    assert "hooks.slack.com" not in out
    assert "ERROR" in out
    assert "2 passed, 1 failed, 1 error" in out


def test_file_timeout_is_inherited(claims, monkeypatch):
    seen = []

    def fake(url, timeout):
        seen.append(timeout)
        return 204

    monkeypatch.setattr("claimcheck.checks.url_status.fetch_status", fake)
    path = claims(
        """
timeout: 12
claims:
  - name: inherited
    type: url_status
    url: https://example.com/health
    status: 204
  - name: local
    type: url_status
    url: https://example.com/health
    status: 204
    timeout: 4
"""
    )
    from claimcheck.run import execute

    assert execute(load_config(path), as_json=False) == 0
    assert seen == [12, 4]
