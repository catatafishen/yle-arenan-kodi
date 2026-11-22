from yleareena.routes import parse_route, plugin_url


def test_plugin_url_is_stable_and_round_trips() -> None:
    url = plugin_url("play", id="programme/123", title="A show")
    assert url.startswith("plugin://plugin.video.ylearenakodi/?")
    assert parse_route(url).item_id == "programme/123"
    assert parse_route(url).action == "play"


def test_invalid_page_defaults_to_one() -> None:
    assert parse_route("plugin://plugin.video.ylearenakodi/?action=search&page=bad").page == 1
