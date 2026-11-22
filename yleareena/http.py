"""Small standard-library HTTP client used by the add-on."""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .errors import YleRequestError


class HttpClient:
    """Fetch JSON and HTML with bounded retries and host validation."""

    def __init__(
            self,
            headers: dict[str, str] | None = None,
            timeout: float = 15.0,
            retries: int = 2,
            allowed_hosts: tuple[str, ...] = ("areena.api.yle.fi", "player.api.yle.fi", "areena.yle.fi",
                                              "arenan.yle.fi", "player-v2.yle.fi"),
    ) -> None:
        self.headers = {"Accept": "application/json", **(headers or {})}
        self.timeout = timeout
        self.retries = max(0, retries)
        self.allowed_hosts = allowed_hosts

    def _request(self, url: str, accept: str) -> bytes:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in self.allowed_hosts:
            raise YleRequestError("Refusing request to an unexpected Yle host")
        headers = {**self.headers, "Accept": accept}
        if parsed.hostname == "player.api.yle.fi":
            # The player API answers "not_allowed" to requests without a web Origin.
            headers.setdefault("Origin", "https://arenan.yle.fi")
        request = Request(url, headers=headers)
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read(8 * 1024 * 1024 + 1)
                    if len(body) > 8 * 1024 * 1024:
                        raise YleRequestError("Yle response exceeded the size limit")
                    return body
            except HTTPError as error:
                if error.code not in {408, 425, 429, 500, 502, 503, 504}:
                    raise YleRequestError(f"Yle request failed with HTTP {error.code}") from error
                last_error = error
            except OSError as error:
                last_error = error
            if attempt < self.retries:
                time.sleep(0.25 * (attempt + 1))
        raise YleRequestError("Yle request failed after retries") from last_error

    def get_json(self, url: str) -> dict[str, Any]:
        try:
            value = json.loads(self._request(url, "application/json"))
        except json.JSONDecodeError as error:
            raise YleRequestError("Yle returned invalid JSON") from error
        if not isinstance(value, dict):
            raise YleRequestError("Yle returned an unexpected JSON document")
        return value

    def get_text(self, url: str) -> str:
        try:
            return self._request(url, "text/html,application/xhtml+xml").decode("utf-8", errors="replace")
        except UnicodeError as error:
            raise YleRequestError("Yle returned invalid text") from error
