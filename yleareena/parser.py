"""Defensive parsers for observed Yle web and player responses."""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote, urlsplit

from .errors import YleResponseError, YleUnavailableError
from .models import AudioTrack, ContentItem, Page, Playback, Subtitle

_PLAYABLE_TYPES = {"programme", "program", "clip", "episode", "video", "recording", "player"}
_IMAGE_CDN = "https://images.cdn.yle.fi/image/upload/w_640,ar_16:9,c_fill"
_CATEGORY_BLOCKS = {"categoryImageLinks", "categoryLinks"}
_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def _labels(card: Mapping[str, Any]) -> dict[str, str]:
    """Return the first raw/formatted value per label type."""
    result: dict[str, str] = {}
    labels = card.get("labels")
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, Mapping):
                kind = _text(label.get("type"))
                value = _first_text(label, "raw", "formatted")
                if kind and value:
                    result.setdefault(kind, value)
    return result


def _duration_seconds(value: str) -> int | None:
    match = _DURATION_RE.match(value)
    if not match or not any(match.groups()):
        return None
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _first_text(data: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(data.get(key))
        if value:
            return value
    return ""


def _first_image(children: Any) -> str:
    """Return the first image URL found among nested image values."""
    for child in children:
        result = _image({"image": child})
        if result:
            return result
    return ""


def _mapping_image(image: Mapping[str, Any]) -> str:
    image_id = _text(image.get("id"))
    if image_id:
        return f"{_IMAGE_CDN}/{image_id}"
    direct = _first_text(image, "url", "src", "original", "large", "16x9")
    if direct:
        return direct
    return _first_image(child for child in image.values() if isinstance(child, Mapping))


def _image(data: Mapping[str, Any]) -> str:
    image = data.get("image") or data.get("images")
    if isinstance(image, str):
        return image
    if isinstance(image, Mapping):
        return _mapping_image(image)
    if isinstance(image, list):
        return _first_image(image)
    return ""


def _formatted_label(card: Mapping[str, Any], kind: str) -> str:
    """Return the display text of the first label of the given type."""
    labels = card.get("labels")
    if not isinstance(labels, list):
        return ""
    return next((
        _text(label.get("formatted")) for label in labels
        if isinstance(label, Mapping) and label.get("type") == kind
    ), "")


def _live_texts(card: Mapping[str, Any], title: str, description: str) -> tuple[str, str]:
    """For a live broadcast card, return (channel title, description of the programme on air)."""
    channel = _formatted_label(card, "broadcastService")
    slot = _formatted_label(card, "generic")
    if not channel:
        return title, description or slot
    # The menu shows the channel; the programme on air and its time go in the description.
    return channel, "\n".join(part for part in (title, slot, description) if part)


def _item_id(pointer: Mapping[str, Any], uri: str) -> str:
    item_id = _first_text(pointer, "id", "identifier")
    if item_id:
        return item_id
    last_segment = urlsplit(uri).path.rstrip("/").rsplit("/", 1)[-1] or uri
    return last_segment.removesuffix(".json")


def _item_from_card(card: Mapping[str, Any]) -> ContentItem | None:
    pointer = card.get("pointer")
    if not isinstance(pointer, Mapping):
        pointer = card.get("target") if isinstance(card.get("target"), Mapping) else {}
    uri = _first_text(pointer, "uri", "url") or _first_text(card, "uri", "url")
    title = _first_text(card, "title", "name")
    if not uri or not title:
        return None
    pointer_type = _first_text(pointer, "type") or _first_text(card, "type")
    description = _first_text(card, "description", "shortDescription", "synopsis")
    if pointer_type == "player":
        title, description = _live_texts(card, title, description)
    duration = card.get("duration")
    if not isinstance(duration, int):
        duration = _duration_seconds(_labels(card).get("duration", ""))
    return ContentItem(
        item_id=_item_id(pointer, uri),
        title=title,
        description=description,
        image=_image(card),
        duration=duration,
        pointer_type=pointer_type,
        uri=uri,
        playable=pointer_type.lower() in _PLAYABLE_TYPES,
        metadata=dict(card),
    )


def parse_search_response(payload: Mapping[str, Any], page: int = 1) -> Page:
    raw_items = payload.get("data")
    if not isinstance(raw_items, list):
        raise YleResponseError("Search response did not contain a data list")
    items = tuple(item for raw in raw_items if isinstance(raw, Mapping) if (item := _item_from_card(raw)) is not None)
    pagination = payload.get("pagination") or payload.get("page") or payload.get("meta") or {}
    has_next = False
    next_page: int | None = None
    if isinstance(pagination, Mapping):
        has_next = bool(pagination.get("hasNext") or pagination.get("has_next") or pagination.get("next"))
        candidate = pagination.get("nextPage") or pagination.get("next_page")
        if isinstance(candidate, int):
            next_page = candidate
        offset, limit, count = (pagination.get(key) for key in ("offset", "limit", "count"))
        if all(isinstance(value, int) for value in (offset, limit, count)) and limit > 0:
            has_next = offset + len(raw_items) < count and bool(raw_items)
    if has_next and next_page is None:
        next_page = page + 1
    return Page(items=items, number=page, has_next=has_next, next_page=next_page)


def _next_data_text(html: str) -> str | None:
    """Return the body of the __NEXT_DATA__ script tag, or None when it is absent."""
    lowered = html.lower()
    for quote in ('"', "'"):
        marker = lowered.find(f"id={quote}__next_data__{quote}")
        if marker != -1:
            break
    else:
        return None
    start = html.find(">", marker)
    end = lowered.find("</script>", start)
    if start == -1 or end == -1:
        return None
    return html[start + 1:end]


def parse_next_data(html: str) -> Mapping[str, Any]:
    text = _next_data_text(html)
    if text is None:
        raise YleResponseError("Areena page did not contain __NEXT_DATA__")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise YleResponseError("Areena __NEXT_DATA__ was invalid JSON") from error
    if not isinstance(value, Mapping):
        raise YleResponseError("Areena __NEXT_DATA__ was not an object")
    return value


def page_sections(html: str) -> list[tuple[str, str, str]]:
    data = parse_next_data(html)
    try:
        view = data["props"]["pageProps"]["view"]
        tabs = view["tabs"]
    except (KeyError, TypeError) as error:
        raise YleResponseError("Areena page did not contain catalogue tabs") from error
    if not isinstance(tabs, list):
        raise YleResponseError("Areena page catalogue tabs were invalid")
    sections: list[tuple[str, str, str]] = []
    for tab_index, tab in enumerate(tabs):
        if not isinstance(tab, Mapping) or not isinstance(tab.get("content"), list):
            continue
        for index, content in enumerate(tab["content"]):
            section = _section(content, _text(tab.get("title")))
            if section:
                sections.append((f"{tab_index}:{index}", *section))
    return sections


def _section(content: Any, tab_title: str) -> tuple[str, str] | None:
    """Return (title, uri) for a public catalogue list, or None for anything else."""
    if not isinstance(content, Mapping) or content.get("type") != "list":
        return None
    source = content.get("source")
    if not isinstance(source, Mapping):
        return None
    authentication = source.get("authentication", [])
    if not isinstance(authentication, list) or "ylelogin" in authentication:
        return None
    uri = _text(source.get("uri"))
    title = _text(content.get("title")) or tab_title
    parsed = urlsplit(uri)
    if not title or parsed.scheme != "https" or parsed.hostname != "areena.api.yle.fi":
        return None
    return title, uri


def _category_item(control: Any, base_url: str) -> ContentItem | None:
    if not isinstance(control, Mapping):
        return None
    destination = control.get("destination")
    title = _text(control.get("title"))
    uri = _text(destination.get("uri")) if isinstance(destination, Mapping) else ""
    package_id = uri.removeprefix("yleareena://packages/")
    if not title or package_id == uri or not package_id or "/" in package_id:
        return None
    return ContentItem(
        item_id=package_id,
        title=title,
        image=_image(control),
        pointer_type="category",
        uri=f"{base_url}/tv/program/{quote(package_id, safe='-')}",
    )


def parse_categories(html: str, base_url: str) -> tuple[ContentItem, ...]:
    """Genre links (Serier, Film, ...) from the site's "Sök och bläddra" menu."""
    try:
        blocks = parse_next_data(html)["props"]["browseMenuContent"]["tvBlocks"]
    except (KeyError, TypeError, YleResponseError):
        return ()
    if not isinstance(blocks, list):
        return ()
    items = (
        _category_item(control, base_url)
        for block in blocks
        if isinstance(block, Mapping) and block.get("type") in _CATEGORY_BLOCKS
        for control in block.get("controls") or ()
    )
    return tuple(item for item in items if item is not None)


def _template(uri: str) -> str:
    """Return the cardOptionsTemplate embedded in a catalogue list token, if any."""
    match = re.search(r"[?&]token=[^.&]+\.([^.&]+)\.", uri)
    if not match:
        return ""
    payload = match.group(1)
    try:
        value = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except ValueError:
        return ""
    return _text(value.get("cardOptionsTemplate")) if isinstance(value, Mapping) else ""


def parse_page_html(html: str, page: int = 1, page_url: str = "https://areena.yle.fi/tv") -> Page:
    sections = [s for s in page_sections(html) if _template(s[2]) != "recommendations"]
    return Page(
        items=tuple(
            ContentItem(item_id=section_id, title=title, pointer_type="section", uri=page_url)
            for section_id, title, _ in sections
        ),
        number=page,
    )


def _tracks(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    return []


_PLAYER_STATES = {
    "pending_ondemand": "Content is not available yet",
    "pending_event": "Event has not started yet",
    "gone": "Content is no longer available",
    "blocked": "Content is blocked",
    "not_allowed": "Playback is not allowed for this content",
    "not_allowed_channel": "Playback is not allowed for this channel",
    "identification": "Sign-in is required for this content",
    "error": "The player service reported an error",
    "ongoing_event": "Live events are not supported",
}


def _raise_player_state(data: Mapping[str, Any]) -> None:
    """Raise the error matching a player response that holds no playable stream."""
    for state, message in _PLAYER_STATES.items():
        if state in data:
            raise YleUnavailableError(message)
    state = _first_text(data, "availability", "state", "status")
    if state:
        raise YleUnavailableError(state)
    raise YleResponseError("Player response did not contain a recognized playback state")


def _subtitles(ongoing: Mapping[str, Any]) -> tuple[Subtitle, ...]:
    values = ongoing.get("subtitles") or ongoing.get("subtitle_tracks") or []
    return tuple(
        Subtitle(
            url=_first_text(track, "url", "src"),
            language=_first_text(track, "language", "lang"),
            label=_first_text(track, "label", "name"),
            is_forced=bool(track.get("forced")),
        )
        for track in _tracks(values)
        if _first_text(track, "url", "src")
    )


def _audio_tracks(ongoing: Mapping[str, Any]) -> tuple[AudioTrack, ...]:
    values = ongoing.get("audio") or ongoing.get("audio_tracks") or []
    return tuple(
        AudioTrack(
            language=_first_text(track, "language", "lang"),
            label=_first_text(track, "label", "name"),
            codec=_first_text(track, "codec", "format"),
        )
        for track in _tracks(values)
    )


def parse_preview_response(payload: Mapping[str, Any]) -> Playback:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise YleResponseError("Player response did not contain data")
    ongoing = data.get("ongoing_ondemand") or data.get("ongoing_channel")
    if not isinstance(ongoing, Mapping):
        _raise_player_state(data)
        raise YleResponseError("Player response did not contain a playable stream")
    manifest_url = _first_text(ongoing, "manifest_url", "manifestUrl", "url")
    if not manifest_url:
        raise YleUnavailableError("No playable manifest was returned")
    parsed = urlsplit(manifest_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise YleResponseError("Player returned an invalid manifest URL")
    protected = bool(
        ongoing.get("is_content_protected") or ongoing.get("protected")
        or ongoing.get("drm") or ongoing.get("content_protection")
    )
    return Playback(
        manifest_url=manifest_url,
        manifest_type=_first_text(ongoing, "manifest_type", "manifestType") or "hls",
        subtitles=_subtitles(ongoing),
        audio_tracks=_audio_tracks(ongoing),
        protected=protected,
        metadata=dict(ongoing),
    )
