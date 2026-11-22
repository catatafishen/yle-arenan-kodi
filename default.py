"""Kodi plugin entry point for Yle Areena."""

from __future__ import annotations

import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from yleareena.config import load_settings
from yleareena.errors import YleError
from yleareena.models import ContentItem, Page
from yleareena.routes import Route, parse_route, plugin_url
from yleareena.service import YleService

HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo("id")


def _label(message_id: int) -> str:
    return ADDON.getLocalizedString(message_id)


def _service() -> YleService:
    settings = load_settings(ADDON)
    return YleService(
        language=settings.language,
        client_id=settings.client_id,
        client_key=settings.client_key,
        player_client_id=settings.player_client_id,
        player_client_key=settings.player_client_key,
    )


def _media_type(item: ContentItem) -> str:
    if item.pointer_type == "player":
        return "video"
    return "episode" if item.playable else "tvshow"


def _action(item: ContentItem) -> str:
    if item.playable:
        return "play"
    if item.pointer_type == "category":
        return "browse_page"
    return "browse_section" if item.pointer_type == "section" else "browse_uri"


def _item_list_item(item: ContentItem) -> xbmcgui.ListItem:
    list_item = xbmcgui.ListItem(label=item.title)
    live = item.pointer_type == "player"
    tag = list_item.getVideoInfoTag()
    tag.setTitle(item.title)
    tag.setMediaType(_media_type(item))
    if live:
        # Live channels have no end, so never let Kodi count them as watched.
        tag.setPlaycount(0)
        list_item.setProperty("IsLive", "true")
    if item.description:
        tag.setPlot(item.description)
    if item.duration is not None:
        tag.setDuration(item.duration)
    if item.image:
        list_item.setArt({"thumb": item.image, "icon": item.image, "poster": item.image, "fanart": item.image})
    return list_item


def _add_content_item(item: ContentItem) -> None:
    url = plugin_url(
        _action(item),
        id=item.item_id,
        uri=item.uri if not item.playable else "",
        title=item.title,
    )
    list_item = _item_list_item(item)
    list_item.setProperty("IsPlayable", "true" if item.playable else "false")
    list_item.addContextMenuItems([
        (_label(30001), f"Container.Update({plugin_url('search')})"),
        (_label(30003), f"RunPlugin({plugin_url('settings')})"),
    ])
    xbmcplugin.addDirectoryItem(HANDLE, url, list_item, isFolder=not item.playable)


def _add_page(page: Page, route: Route | None = None, extra: tuple[ContentItem, ...] = ()) -> None:
    for item in page.items:
        _add_content_item(item)
    if page.has_next and page.next_page and route:
        url = plugin_url(route.action, q=route.query, id=route.item_id, uri=route.uri, page=page.next_page)
        xbmcplugin.addDirectoryItem(HANDLE, url, xbmcgui.ListItem(label=_label(30004)), isFolder=True)
    for item in extra:
        _add_content_item(item)
    if not page.items and not extra:
        xbmcplugin.addDirectoryItem(HANDLE, plugin_url("root"), xbmcgui.ListItem(label=_label(30009)), isFolder=False)
    if page.items and all(item.playable for item in page.items):
        xbmcplugin.setContent(HANDLE, "episodes")
    elif page.items and all(item.pointer_type != "section" for item in page.items):
        xbmcplugin.setContent(HANDLE, "tvshows")
    else:
        xbmcplugin.setContent(HANDLE, "videos")
    xbmcplugin.endOfDirectory(HANDLE)


def _browse_uri(route: Route, service: YleService) -> None:
    """Show a page's first list (e.g. a series' episodes) directly, with other lists as folders."""
    page = service.browse_uri(route.uri, route.page)
    sections = [item for item in page.items if item.pointer_type == "section"]
    if not sections or len(sections) != len(page.items):
        _add_page(page, route)
        return
    first = sections[0]
    content = service.browse_section(route.uri, first.item_id)
    others = tuple(sections[1:]) if route.page == 1 else ()
    _add_page(content, Route(action="browse_uri", uri=route.uri, page=route.page), extra=others)


def _search(route: Route, service: YleService) -> None:
    query = route.query
    if not query:
        query = xbmcgui.Dialog().input(_label(30005), type=xbmcgui.INPUT_ALPHANUM)
    if query:
        _add_page(service.search(query))
    else:
        xbmcplugin.endOfDirectory(HANDLE)


def _play(route: Route, service: YleService) -> None:
    playback = service.resolve(route.item_id)
    list_item = xbmcgui.ListItem(path=playback.manifest_url)
    list_item.setProperty("inputstream", "inputstream.adaptive")
    list_item.setProperty("inputstream.adaptive.manifest_type", playback.manifest_type)
    if playback.subtitles:
        list_item.setSubtitles([track.url for track in playback.subtitles])
    xbmcplugin.setResolvedUrl(HANDLE, True, list_item)


def _dispatch(route: Route) -> None:
    if route.action == "settings":
        ADDON.openSettings()
        return
    service = _service()
    if route.action in ("root", "browse_tv"):
        _add_page(service.browse_tv(route.page))
    elif route.action == "search":
        _search(route, service)
    elif route.action == "browse_page" and route.uri:
        _add_page(service.browse_page(route.uri))
    elif route.action == "browse_uri" and route.uri:
        _browse_uri(route, service)
    elif route.action == "browse_section" and route.uri and route.item_id:
        _add_page(service.browse_section(route.uri, route.item_id))
    elif route.action == "play" and route.item_id:
        _play(route, service)
    else:
        _add_page(service.browse_tv(route.page))


def _fail(route: Route | None) -> None:
    if route and route.action == "play":
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
    else:
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


def main() -> None:
    route = None
    try:
        raw = sys.argv[2] if len(sys.argv) > 2 else ""
        route = parse_route(raw)
        _dispatch(route)
    except YleError as error:
        xbmc.log(f"{ADDON_ID}: {error}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok(_label(30007), str(error))
        _fail(route)
    except (AttributeError, TypeError, ValueError, RuntimeError) as error:
        xbmc.log(f"{ADDON_ID}: unexpected integration error: {error}", xbmc.LOGERROR)
        xbmcgui.Dialog().ok(_label(30007), str(error))
        _fail(route)


if __name__ == "__main__":
    main()
