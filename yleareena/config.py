"""Configuration bridge with a safe non-Kodi fallback for tests."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    language: str = "sv"
    client_id: str = ""
    client_key: str = ""
    player_client_id: str = ""
    player_client_key: str = ""
    user_agent: str = "YleAreenaKodi/0.1"


def load_settings(addon=None) -> Settings:
    if addon is None:
        return Settings()
    return Settings(
        language=addon.getSetting("language").strip() or "sv",
        client_id=addon.getSetting("client_id").strip(),
        client_key=addon.getSetting("client_key").strip(),
        player_client_id=addon.getSetting("player_client_id").strip(),
        player_client_key=addon.getSetting("player_client_key").strip(),
        user_agent=addon.getSetting("user_agent").strip() or "YleAreenaKodi/0.1",
    )
