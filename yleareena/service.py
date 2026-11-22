"""Yle catalogue and playback service."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from .errors import YleConfigurationError, YleError, YleResponseError
from .http import HttpClient
from .models import ContentItem, Page, Playback
from .parser import (
    page_sections,
    parse_categories,
    parse_page_html,
    parse_preview_response,
    parse_search_response,
)

SEARCH_URL = "https://areena.api.yle.fi/v1/ui/search"
PREVIEW_URL = "https://player.api.yle.fi/v1/preview/{id}.json"
PAGE_HOSTS = {"sv": "arenan.yle.fi", "fi": "areena.yle.fi"}
PAGE_SIZE = 25
MAX_PAGES = 10


class YleService:
    """Fetch catalogue data and resolve a fresh playback URL."""

    def __init__(
            self, client: HttpClient | None = None, client_id: str = "", client_key: str = "",
            player_client_id: str = "", player_client_key: str = "", language: str = "sv",
    ) -> None:
        if language not in PAGE_HOSTS:
            raise YleConfigurationError("Unsupported content language")
        self.language = language
        self.client = client or HttpClient()
        self.client_id = client_id
        self.client_key = client_key
        self.player_client_id = player_client_id
        self.player_client_key = player_client_key

    def _ensure_credentials(self) -> None:
        if not self.client_id or not self.client_key:
            raise YleConfigurationError("Configure a Yle client ID and client key in add-on settings")

    def _catalogue_url(self, url: str, **params: str) -> str:
        self._ensure_credentials()
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != "areena.api.yle.fi":
            raise YleResponseError("Unexpected catalogue source host")
        query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
                 if key not in {"app_id", "app_key", *params}]
        query.extend(params.items())
        query.extend((("app_id", self.client_id), ("app_key", self.client_key)))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))

    def _page_url(self, uri: str) -> str:
        parts = urlsplit(uri)
        if parts.scheme == "yleareena" and parts.netloc in ("items", "packages"):
            item_id = parts.path.strip("/")
            if item_id and "/" not in item_id and not parts.query and not parts.fragment:
                prefix = "tv/program/" if parts.netloc == "packages" else ""
                return f"https://{PAGE_HOSTS[self.language]}/{prefix}{quote(item_id, safe='-')}"
        if parts.scheme == "https" and parts.netloc in PAGE_HOSTS.values():
            return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
        raise YleResponseError("Unsupported Arenan or Areena page link")

    @staticmethod
    def _all_pages(fetch: Callable[[int], Page]) -> Page:
        """Fetch consecutive pages and merge them so Kodi shows one continuous list."""
        items: list[ContentItem] = []
        for number in range(1, MAX_PAGES + 1):
            page = fetch(number)
            items.extend(page.items)
            if not page.has_next:
                break
        return Page(items=tuple(items))

    def search(self, query: str) -> Page:
        return self._all_pages(lambda number: self._search_page(query, number))

    def _search_page(self, query: str, page: int) -> Page:
        params = {
            "query": query,
            "client": "yle-areena-web",
            "language": self.language,
            "v": "10",
            "limit": str(PAGE_SIZE),
            "offset": str((max(1, page) - 1) * PAGE_SIZE),
        }
        return parse_search_response(self.client.get_json(self._catalogue_url(SEARCH_URL, **params)), page=page)

    def browse_tv(self, page: int = 1) -> Page:
        base = f"https://{PAGE_HOSTS[self.language]}"
        html = self.client.get_text(f"{base}/tv")
        items = self._sections_with_previews(html, f"{base}/tv", page)
        categories = parse_categories(html, base)
        return Page(items=self._live_channels() + categories + items.items, number=page)

    def browse_page(self, uri: str) -> Page:
        """A category page: its lists as folders, each previewed by its first entries."""
        url = self._page_url(uri)
        return self._sections_with_previews(self.client.get_text(url), url, 1)

    def _sections_with_previews(self, html: str, url: str, page: int) -> Page:
        result = parse_page_html(html, page=page, page_url=url)
        sources = {key: uri for key, _, uri in page_sections(html)}
        with ThreadPoolExecutor(max_workers=8) as pool:
            items = tuple(pool.map(lambda item: self._with_preview(item, sources.get(item.item_id, "")), result.items))
        return Page(items=items, number=page)

    def _live_channels(self) -> tuple[ContentItem, ...]:
        """Currently airing TV channels from the Direkt page; never blocks the rest of the menu."""
        try:
            html = self.client.get_text(f"https://{PAGE_HOSTS[self.language]}/direkt")
            source = next(
                (uri for _, _, uri in page_sections(html) if "schedules/now" in uri and "yle-tv" in uri), "")
            if not source:
                return ()
            items = parse_search_response(self.client.get_json(self._catalogue_url(source))).items
        except (YleError, ValueError):
            return ()
        return tuple(item for item in items if item.playable)

    def _with_preview(self, item: ContentItem, source: str) -> ContentItem:
        """Give a section the artwork of its first entry and a list of its first titles."""
        if not source:
            return item
        try:
            api_url = self._catalogue_url(source, limit="4", offset="0")
            first = parse_search_response(self.client.get_json(api_url)).items
        except (YleError, ValueError):
            return item
        if not first:
            return item
        return replace(item, image=first[0].image, description="\n".join(entry.title for entry in first))

    def browse_uri(self, uri: str, page: int = 1) -> Page:
        url = self._page_url(uri)
        return parse_page_html(self.client.get_text(url), page=page, page_url=url)

    def browse_section(self, page_uri: str, section_id: str) -> Page:
        url = self._page_url(page_uri)
        sections = page_sections(self.client.get_text(url))
        source = next((uri for key, _, uri in sections if key == section_id), None)
        if source is None:
            raise YleResponseError("This catalogue section is no longer available")

        def fetch(number: int) -> Page:
            api_url = self._catalogue_url(source, limit=str(PAGE_SIZE), offset=str((number - 1) * PAGE_SIZE))
            return parse_search_response(self.client.get_json(api_url), page=number)

        return self._all_pages(fetch)

    def resolve(self, item_id: str) -> Playback:
        if not self.player_client_id or not self.player_client_key:
            raise YleConfigurationError("Configure the Yle player client ID and key in add-on settings")
        safe_id = quote(item_id, safe="")
        params = urlencode({
            "app_id": self.player_client_id,
            "app_key": self.player_client_key,
            "language": "swe" if self.language == "sv" else "fin",
            "countryCode": "FI",
            "host": PAGE_HOSTS[self.language],
            "isMobile": "false",
            "isPortabilityRegion": "true",
            "ssl": "true",
        })
        return parse_preview_response(self.client.get_json(PREVIEW_URL.format(id=safe_id) + "?" + params))
