import json
import pytest
from urllib.parse import parse_qs, urlsplit

from yleareena.config import load_settings
from yleareena.errors import YleConfigurationError, YleResponseError
from yleareena.service import YleService


def page_html() -> str:
    data = {"props": {"pageProps": {"view": {"tabs": [{"content": [
        {"type": "list", "title": "Series", "source": {
            "uri": "https://areena.api.yle.fi/v1/ui/content/list?token=short-lived",
            "authentication": ["yle-api"],
        }},
        {"type": "list", "title": "Account", "source": {
            "uri": "https://areena.api.yle.fi/v1/ui/profile/favorites",
            "authentication": ["yle-api", "ylelogin"],
        }},
    ]}]}}}, "footer": {"title": "Yle", "url": "https://yle.fi"}}
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + '</script>'


class FakeClient:
    def __init__(self) -> None:
        self.json_urls: list[str] = []
        self.text_urls: list[str] = []

    def get_json(self, url: str) -> dict:
        self.json_urls.append(url)
        offset = int(parse_qs(urlsplit(url).query).get("offset", ["0"])[0])
        total = 30
        count = min(25, total - offset)
        return {
            "data": [
                {"pointer": {"type": "series", "uri": f"yleareena://items/1-{offset + i + 1}"},
                 "title": f"Series {offset + i + 1}"}
                for i in range(count)
            ],
            "meta": {"offset": offset, "limit": 25, "count": total},
        }

    def get_text(self, url: str) -> str:
        self.text_urls.append(url)
        return page_html()


def test_search_merges_all_pages() -> None:
    client = FakeClient()
    service = YleService(client=client, client_id="id", client_key="key", language="fi")
    page = service.search("news")
    offsets = [parse_qs(urlsplit(url).query)["offset"] for url in client.json_urls]
    params = parse_qs(urlsplit(client.json_urls[0]).query)
    assert offsets == [["0"], ["25"]]
    assert len(page.items) == 30
    assert not page.has_next
    assert page.items[0].item_id == "1-1"
    assert page.items[-1].item_id == "1-30"
    assert params["query"] == ["news"]
    assert params["language"] == ["fi"]
    assert params["app_id"] == ["id"]
    assert params["app_key"] == ["key"]


def test_tv_sections_exclude_footer_and_logged_in_lists() -> None:
    client = FakeClient()
    service = YleService(client=client)
    page = service.browse_tv()
    assert [(item.title, item.item_id) for item in page.items] == [("Series", "0:0")]
    assert "short-lived" not in page.items[0].uri
    with pytest.raises(YleConfigurationError):
        service.browse_section(page.items[0].uri, page.items[0].item_id)


@pytest.mark.parametrize("host", ["arenan.yle.fi", "areena.yle.fi"])
def test_section_refetches_source_and_merges_pages(host: str) -> None:
    client = FakeClient()
    service = YleService(client=client, client_id="id", client_key="key")
    page = service.browse_section(f"https://{host}/tv", "0:0")
    assert client.text_urls == [f"https://{host}/tv"]
    params = parse_qs(urlsplit(client.json_urls[0]).query)
    assert params["token"] == ["short-lived"]
    assert len(page.items) == 30
    assert not page.has_next


def test_player_uses_separate_credentials() -> None:
    class PlayerClient(FakeClient):
        def get_json(self, url: str) -> dict:
            self.json_urls.append(url)
            return {"data": {"ongoing_ondemand": {"manifest_url": "https://cdn.example.test/video.m3u8"}}}

    client = PlayerClient()
    service = YleService(client=client, client_id="catalogue", client_key="catalogue-key",
                         player_client_id="player", player_client_key="player-key")
    service.resolve("1-123")
    query = parse_qs(urlsplit(client.json_urls[0]).query)
    assert query["app_id"] == ["player"]
    assert query["app_key"] == ["player-key"]
    assert query["countryCode"] == ["FI"]
    assert query["isPortabilityRegion"] == ["true"]
    unconfigured = YleService(client=client, client_id="catalogue", client_key="catalogue-key")
    with pytest.raises(YleConfigurationError):
        unconfigured.resolve("1-123")


@pytest.mark.parametrize(("language", "host"), [("sv", "arenan.yle.fi"), ("fi", "areena.yle.fi")])
def test_tv_and_series_use_selected_service(language: str, host: str) -> None:
    client = FakeClient()
    service = YleService(client=client, language=language)
    service.browse_tv()
    service.browse_uri("yleareena://items/1-123")
    assert client.text_urls == [f"https://{host}/tv", f"https://{host}/direkt", f"https://{host}/1-123"]
    with pytest.raises(YleResponseError):
        service.browse_uri("https://example.com/")


def test_existing_settings_default_to_swedish() -> None:
    class Addon:
        @staticmethod
        def getSetting(name: str) -> str:
            return {"client_id": "existing-id", "client_key": "existing-key"}.get(name, "")

    settings = load_settings(Addon())
    assert settings.language == "sv"
    assert settings.client_id == "existing-id"
    assert settings.client_key == "existing-key"


def test_default_content_language_is_swedish() -> None:
    client = FakeClient()
    YleService(client=client).browse_tv()
    assert client.text_urls == ["https://arenan.yle.fi/tv", "https://arenan.yle.fi/direkt"]
    with pytest.raises(YleConfigurationError):
        YleService(client=client, language="en")


def test_live_channels_are_listed_first_and_playable() -> None:
    class LiveClient(FakeClient):
        def get_text(self, url: str) -> str:
            self.text_urls.append(url)
            if url.endswith("/direkt"):
                data = {"props": {"pageProps": {"view": {"tabs": [{"content": [{
                    "type": "list", "title": "TV-kanaler", "source": {
                        "uri": "https://areena.api.yle.fi/v1/ui/schedules/now.json?service=yle-tv1,yle-tv2",
                        "authentication": ["yle-api"]}}]}]}}}}
                return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + '</script>'
            return page_html()

        def get_json(self, url: str) -> dict:
            if "schedules/now" in url:
                return {"data": [{
                    "title": "News",
                    "pointer": {"type": "player", "uri": "https://areena.api.yle.fi/v1/ui/players/yle-tv1.json?v=10"},
                    "labels": [{"type": "broadcastService", "formatted": "Yle TV1", "raw": "yle-tv1"}],
                }]}
            return super().get_json(url)

    page = YleService(client=LiveClient(), client_id="id", client_key="key").browse_tv()
    channel = page.items[0]
    assert (channel.item_id, channel.title, channel.playable) == ("yle-tv1", "Yle TV1", True)
    assert channel.description == "News"
    assert page.items[1].pointer_type == "section"
