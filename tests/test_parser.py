import json
import pytest

from yleareena.errors import YleResponseError, YleUnavailableError
from yleareena.parser import parse_categories, parse_next_data, parse_preview_response, parse_search_response


def test_search_response_parses_cards_and_pagination() -> None:
    page = parse_search_response(
        {
            "data": [
                {
                    "pointer": {"type": "programme", "id": "p1", "uri": "https://areena.yle.fi/1-1"},
                    "title": "Programme",
                    "description": "Description",
                },
                {
                    "pointer": {"type": "series", "uri": "https://areena.yle.fi/1-2"},
                    "title": "Series",
                },
            ],
            "pagination": {"hasNext": True, "nextPage": 3},
        },
        page=2,
    )
    assert [item.title for item in page.items] == ["Programme", "Series"]
    assert page.items[0].playable is True
    assert page.items[1].playable is False
    assert page.next_page == 3


def test_catalogue_pagination_uses_meta_offsets() -> None:
    page = parse_search_response({
        "data": [{"pointer": {"type": "series", "uri": "yleareena://items/1-1"}, "title": "A"}],
        "meta": {"offset": 0, "limit": 25, "count": 30},
    })
    assert page.has_next
    assert page.next_page == 2
    assert page.items[0].item_id == "1-1"


def test_image_and_iso_duration_are_extracted_from_cards() -> None:
    page = parse_search_response({"data": [{
        "pointer": {"type": "program", "uri": "yleareena://items/1-9"},
        "title": "Episode",
        "image": {"id": "13-1-9-111", "version": "5"},
        "labels": [{"type": "duration", "formatted": "5 min", "raw": "PT1H2M3S"}],
    }]})
    item = page.items[0]
    assert item.image.endswith("/13-1-9-111")
    assert item.image.startswith("https://")
    assert item.duration == 3723
    assert item.playable


def test_categories_are_read_from_the_browse_menu() -> None:
    data = {"props": {"browseMenuContent": {"tvBlocks": [
        {"type": "categoryImageLinks", "controls": [{
            "title": "Film", "destination": {"uri": "yleareena://packages/57-abc"},
            "image": {"id": "13-57-1", "version": "0"}}]},
        {"type": "categoryLinks", "controls": [{
            "title": "Syntolkat", "destination": {"uri": "yleareena://packages/57-def"}}]},
        {"type": "textLinks", "controls": [{
            "title": "Fler program", "destination": {"uri": "yleareena://packages/30-5192"}}]},
    ]}}}
    html = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + '</script>'
    film, accessible = parse_categories(html, "https://arenan.yle.fi")
    assert film.title == "Film"
    assert film.pointer_type == "category"
    assert film.uri == "https://arenan.yle.fi/tv/program/57-abc"
    assert film.image.endswith("/13-57-1")
    assert accessible.title == "Syntolkat"
    assert parse_categories("<html></html>", "https://arenan.yle.fi") == ()


def test_next_data_requires_expected_script() -> None:
    with pytest.raises(YleResponseError):
        parse_next_data("<html></html>")


def test_preview_parses_manifest_subtitles_and_audio() -> None:
    playback = parse_preview_response(
        {
            "data": {
                "ongoing_ondemand": {
                    "manifest_url": "https://cdn.example.test/master.m3u8",
                    "subtitles": [{"url": "https://cdn.example.test/fi.vtt", "language": "fi"}],
                    "audio_tracks": [{"language": "fi", "label": "Suomi"}],
                }
            }
        }
    )
    assert playback.manifest_type == "hls"
    assert playback.subtitles[0].language == "fi"
    assert playback.audio_tracks[0].label == "Suomi"


def test_preview_recognizes_content_protection() -> None:
    playback = parse_preview_response({"data": {"ongoing_ondemand": {
        "manifest_url": "https://cdn.example.test/master.m3u8",
        "is_content_protected": True,
    }}})
    assert playback.protected


def test_preview_accepts_live_channel() -> None:
    playback = parse_preview_response({"data": {"ongoing_channel": {
        "manifest_url": "https://cdn.example.test/live/index.m3u8"}}})
    assert playback.manifest_url.endswith("index.m3u8")


def test_preview_rejects_missing_availability() -> None:
    with pytest.raises(YleUnavailableError):
        parse_preview_response({"data": {"availability": "expired"}})


@pytest.mark.parametrize(("state", "message"), [
    ("pending_ondemand", "not available yet"),
    ("gone", "no longer available"),
    ("blocked", "blocked"),
    ("not_allowed", "not allowed"),
    ("identification", "Sign-in is required"),
    ("error", "player service reported an error"),
])
def test_preview_reports_player_state(state: str, message: str) -> None:
    with pytest.raises(YleUnavailableError, match=message):
        parse_preview_response({"data": {state: {}}})


def test_preview_rejects_unknown_response_state() -> None:
    with pytest.raises(YleResponseError, match="recognized playback state"):
        parse_preview_response({"data": {"unexpected": {}}})
