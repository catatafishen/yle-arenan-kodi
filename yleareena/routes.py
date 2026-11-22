"""Stable plugin URL construction and parsing."""

from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit


PLUGIN_ID = "plugin.video.ylearenakodi"


@dataclass(frozen=True)
class Route:
    action: str = "root"
    item_id: str = ""
    query: str = ""
    page: int = 1
    uri: str = ""


def plugin_url(action: str = "root", **values: object) -> str:
    params: dict[str, str] = {"action": action}
    for key, value in values.items():
        if value is not None and value != "":
            params[key] = str(value)
    return f"plugin://{PLUGIN_ID}/?{urlencode(params)}"


def parse_route(raw: str) -> Route:
    query = parse_qs(urlsplit(raw).query, keep_blank_values=True)
    action = query.get("action", ["root"])[0] or "root"
    try:
        page = max(1, int(query.get("page", ["1"])[0]))
    except ValueError:
        page = 1
    return Route(
        action=action,
        item_id=query.get("id", [""])[0],
        query=query.get("q", [""])[0],
        page=page,
        uri=query.get("uri", [""])[0],
    )
