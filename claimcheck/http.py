"""HTTP status fetch. Redirects are not followed. URLs stay out of messages."""

from __future__ import annotations

import socket
import urllib.error
import urllib.request

from claimcheck import __version__
from claimcheck.errors import CheckError

USER_AGENT = f"claimcheck/{__version__}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Report the first status. A 301 is not turned into the next hop's code."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


def fetch_status(url: str, timeout: float) -> int:
    """Return the HTTP status for one GET. Network errors raise CheckError."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with _open(request, timeout) as response:
            response.read(1024)
            return int(response.status)
    except urllib.error.HTTPError as exc:
        try:
            return int(exc.code)
        finally:
            exc.close()
    except (TimeoutError, socket.timeout) as exc:
        raise CheckError(f"timed out after {timeout:g}s") from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise CheckError(f"timed out after {timeout:g}s") from exc
        text = " ".join(str(reason).split()) or "request failed"
        if len(text) > 200:
            text = text[:197] + "..."
        raise CheckError(f"fetch failed: {text}") from exc


def _open(request, timeout):
    opener = urllib.request.build_opener(_NoRedirect)
    return opener.open(request, timeout=timeout)
