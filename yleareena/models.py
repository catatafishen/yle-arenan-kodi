"""Data models shared by the parser, service, and Kodi adapter."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContentItem:
    """A catalogue item represented by a stable navigation URL."""

    item_id: str
    title: str
    description: str = ""
    image: str = ""
    duration: int | None = None
    pointer_type: str = ""
    uri: str = ""
    playable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Page:
    """A page of catalogue items."""

    items: tuple[ContentItem, ...]
    number: int = 1
    has_next: bool = False
    next_page: int | None = None


@dataclass(frozen=True)
class Subtitle:
    """A subtitle track returned by the player preview."""

    url: str
    language: str = ""
    label: str = ""
    is_forced: bool = False


@dataclass(frozen=True)
class AudioTrack:
    """An audio track returned by the player preview."""

    language: str = ""
    label: str = ""
    codec: str = ""


@dataclass(frozen=True)
class Playback:
    """Resolved playback information for a single item."""

    manifest_url: str
    manifest_type: str = "hls"
    subtitles: tuple[Subtitle, ...] = ()
    audio_tracks: tuple[AudioTrack, ...] = ()
    protected: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
