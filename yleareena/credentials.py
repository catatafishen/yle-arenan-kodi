"""Read the application credentials a browser would use from Yle's public web assets."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from .errors import YleResponseError

PLAYER_BUNDLE_URL = "https://player-v2.yle.fi/embed.js"
_ENV_MARKER = "window.envVariables"
_PLAYER_KEYS_RE = re.compile(r"app_id=(player\w+)&app_key=(\w+)")


class TextClient(Protocol):
    """Anything that can fetch a page as text, such as HttpClient."""

    def get_text(self, url: str) -> str: ...


@dataclass(frozen=True)
class Credentials:
    """The catalogue and player application credentials served to web browsers."""

    client_id: str
    client_key: str
    player_client_id: str
    player_client_key: str


def _page_credentials(html: str) -> tuple[str, str]:
    """Return (app id, app key) from the page's inline window.envVariables script."""
    marker = html.find(_ENV_MARKER)
    start = html.find("{", marker) if marker != -1 else -1
    if start == -1:
        raise YleResponseError("Yle page did not contain its client configuration")
    try:
        variables, _ = json.JSONDecoder().raw_decode(html, start)
    except ValueError as error:
        raise YleResponseError("Yle client configuration was invalid") from error
    app_id = variables.get("appIdFrontend") if isinstance(variables, dict) else None
    app_key = variables.get("appKeyFrontend") if isinstance(variables, dict) else None
    if not isinstance(app_id, str) or not isinstance(app_key, str) or not app_id or not app_key:
        raise YleResponseError("Yle client configuration did not contain application credentials")
    return app_id, app_key


def _chunk_urls(bundle: str) -> list[str]:
    """Chunk URLs the player bundle loads, taken from its webpack runtime."""
    runtime = bundle.find(".u=function(")
    path_start = bundle.find('.p="')
    if runtime == -1 or path_start == -1:
        return []
    path_start += len('.p="')
    base = bundle[path_start:bundle.find('"', path_start)]
    open_brace = bundle.find("{", runtime)
    close_brace = bundle.find("}", open_brace)
    if open_brace == -1 or close_brace == -1:
        return []
    urls = []
    for entry in bundle[open_brace + 1:close_brace].split(","):
        chunk, _, digest = entry.partition(":")
        digest = digest.strip('"')
        if chunk.isdigit() and digest.isalnum():
            urls.append(f"{base}{chunk}.{digest}.js")
    return urls


def _player_credentials(client: TextClient) -> tuple[str, str]:
    """Return (app id, app key) for the player API from the player bundle."""
    for url in _chunk_urls(client.get_text(PLAYER_BUNDLE_URL)):
        match = _PLAYER_KEYS_RE.search(client.get_text(url))
        if match:
            return match.group(1), match.group(2)
    raise YleResponseError("Yle player bundle did not contain application credentials")


def fetch_credentials(client: TextClient, page_url: str) -> Credentials:
    """Fetch the credentials the Yle website serves to a browser in the caller's region."""
    client_id, client_key = _page_credentials(client.get_text(page_url))
    player_id, player_key = _player_credentials(client)
    return Credentials(client_id, client_key, player_id, player_key)
