import json
import pytest

from yleareena.credentials import fetch_credentials
from yleareena.errors import YleRequestError, YleResponseError

PAGE = (
        "<html><script>window.envVariables = "
        + json.dumps({"appIdFrontend": "web-id", "appKeyFrontend": "web-key", "brazeSdkApiKey": "ignored"})
        + ";</script></html>"
)
BUNDLE = (
    'o.u=function(t){return t+"."+{33:"aaa111",761:"bbb222"}[t]+".js"},o.p="https://player.example/",'
)
CHUNKS = {
    "https://player.example/33.aaa111.js": "nothing useful here",
    "https://player.example/761.bbb222.js": 'x=new URLSearchParams("app_id=player_prod&app_key=secret123")',
}


class FakeClient:
    def __init__(self, page: str = PAGE, bundle: str = BUNDLE) -> None:
        self.pages = {
            "https://arenan.yle.fi/tv": page,
            "https://player-v2.yle.fi/embed.js": bundle,
            **CHUNKS,
        }
        self.requested: list[str] = []

    def get_text(self, url: str) -> str:
        self.requested.append(url)
        if url not in self.pages:
            raise YleRequestError("not found")
        return self.pages[url]


def test_credentials_are_read_from_page_and_player_bundle() -> None:
    credentials = fetch_credentials(FakeClient(), "https://arenan.yle.fi/tv")
    assert credentials.client_id == "web-id"
    assert credentials.client_key == "web-key"
    assert credentials.player_client_id == "player_prod"
    assert credentials.player_client_key == "secret123"


def test_page_without_configuration_is_rejected() -> None:
    client = FakeClient(page="<html></html>")
    with pytest.raises(YleResponseError, match="client configuration"):
        fetch_credentials(client, "https://arenan.yle.fi/tv")


def test_page_without_application_credentials_is_rejected() -> None:
    client = FakeClient(page='<script>window.envVariables = {"versionNumber": "1"};</script>')
    with pytest.raises(YleResponseError, match="application credentials"):
        fetch_credentials(client, "https://arenan.yle.fi/tv")


def test_player_bundle_without_credentials_is_rejected() -> None:
    client = FakeClient()
    client.pages["https://player.example/761.bbb222.js"] = "nothing here either"
    with pytest.raises(YleResponseError, match="player bundle"):
        fetch_credentials(client, "https://arenan.yle.fi/tv")
