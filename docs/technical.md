# Technical notes

This document records how Yle's web and player interfaces behave, as observed in a browser and from the add-on while
building it. The interfaces are undocumented implementation details and may change without notice. Observations were
made on 22 November 2026 from Finland, without signing in, spoofing a location, or bypassing access controls or DRM.

## Pages and catalogue data

Yle Arenan (`arenan.yle.fi`) is the Swedish-language service and Yle Areena (`areena.yle.fi`) is the Finnish-language
service. They are separate sites with different curated sections, not translations of each other. The add-on uses
Arenan by default; the content language setting switches the host and the API language.

Every page embeds a `__NEXT_DATA__` JSON object. Its structure, as used by the add-on:

- `props.pageProps.view.tabs[].content[]` holds the page's blocks. Blocks of `type: "list"` have a `source.uri` that
  points at the catalogue API and an `authentication` list. Lists that need `ylelogin` are personal ("Min lista",
  continue watching) and are skipped.
- A list's `source.uri` carries a signed `token`. Its payload contains a `cardOptionsTemplate`, which tells the kind of
  list. `recommendations` is the "Se mer" similar-content list and is skipped; `episodes` is a series' episode list.
- `props.browseMenuContent.tvBlocks` is the "Sök och bläddra" menu. Blocks of type `categoryImageLinks` and
  `categoryLinks` hold the genres (Serier, Film, Dokumentärer, ...) as `yleareena://packages/<id>` links. A genre page
  is `/tv/program/<id>` and has the same shape as the TV page.
- `props.pageProps` also holds `view`, `meta`, `selectedTab` and the service name. The add-on fetches pages with plain
  HTTP, not a browser, so everything it needs has to be in this payload or in the API responses it links to.

Section ids used by the add-on are `<tab index>:<content index>`, so they are only stable for the same page version.
Because of that, folders refetch the page and look the section up again instead of storing the signed token.

### Catalogue API

```text
https://areena.api.yle.fi/v1/ui/search
https://areena.api.yle.fi/v1/ui/content/list?token=...
```

Both return `data`, an array of cards, and `meta` with `offset`, `limit` and `count`. Pages are 25 items; the add-on
fetches consecutive pages (up to 10) and merges them so Kodi shows one list. A card has a `pointer` (`type` and `uri`
such as `yleareena://items/1-123`), a `title`, a `description` and labels. Pointer types `program`, `programme`,
`clip` and `episode` are playable; `series` and packages open another page.

Durations are in the card's `labels` as ISO 8601 (`PT1H2M3S`). Not every card has one.

### Images

Images are given as `{id, version}`, not a URL. This builds a working 16:9 URL:

```text
https://images.cdn.yle.fi/image/upload/w_640,ar_16:9,c_fill/<id>
```

### Live channels

The Direkt page (`/direkt`) has a "TV-kanaler" list at `areena.api.yle.fi/v1/ui/schedules/now.json?service=yle-tv1,...`.
Its cards have `pointer.type: "player"` and a `.../players/yle-tv1.json` URI. The programme on air is the card title,
the channel is in the `broadcastService` label and the time slot in the `generic` label. The add-on shows the channel as
the item title and the programme and time in the plot. The list changes through the day, so it is fetched each time the
menu opens. There are also a "Sport" list and radio channels on Direkt that are not used.

## Credentials

Both APIs need an application id and key. Requests without them return HTTP 403. They are public values that Yle's own
website hands to every browser:

| Pair                           | Where the browser gets it                                                                |
|--------------------------------|------------------------------------------------------------------------------------------|
| Catalogue (`areena-web-items`) | `window.envVariables.appIdFrontend` and `appKeyFrontend`, an inline script on every page |
| Player (`player_static_prod`)  | A string in the player bundle `https://player-v2.yle.fi/embed.js` and its chunks         |

The player chunk filenames contain a content hash. The add-on reads the chunk list from the webpack runtime in
`embed.js` instead of hardcoding a name. The settings page has a button that fetches both pairs over HTTP from the
user's own machine, so the values are what Yle serves to a browser in that region. They are not stored in the
repository.

There is no public Yle media API. See Yle's [developer documentation](https://developer.yle.fi/en/api/index.html).

## Player preview

```text
https://player.api.yle.fi/v1/preview/{id}.json
```

The id is a programme id (`1-76547052`) or a channel id (`yle-tv1`). The browser sends these query parameters, and the
add-on sends the same ones:

```text
app_id, app_key, language=swe|fin, countryCode=FI, host=arenan.yle.fi|areena.yle.fi,
isMobile=false, isPortabilityRegion=true, ssl=true
```

### The `Origin` header

This is the one detail that mattered for playback. With the same URL, parameters and IP address, the API returns
`not_allowed` to a plain request and a playable response to a request that has an `Origin` header with any Yle site.
`Referer`, `User-Agent`, cookies and other browser headers made no difference. The add-on sends
`Origin: https://arenan.yle.fi` on `player.api.yle.fi` requests. Responses are also cached for about 30 seconds, so
test header changes with a cache-busting parameter.

### Response states

The result is one key under `data`:

- `ongoing_ondemand` - an on-demand programme. Contains `manifest_url`, audio tracks and subtitles.
- `ongoing_channel` - a live channel. Contains `manifest_url` and a `dvr_window_in_seconds` (4 hours for the TV
  channels).
- `not_allowed`, `not_allowed_channel`, `blocked`, `gone`, `pending_ondemand`, `pending_event`, `identification` and
  `error` - the content cannot be played. The add-on reports each in its own message.
- `ongoing_event` - a live event, which the add-on does not support.

### Manifests

`manifest_url` is an HLS master playlist on Akamai (`yleawsmpondemand-*.akamaized.net` for on demand,
`yletv.akamaized.net/hls/live/...` for TV channels). It is signed and temporary, so it is requested when playback starts
and is never stored, put in a favourite, committed or logged. Kodi fetches it without an `Origin` header.

`is_content_protected: true` is set on many programmes, including ones that play normally. The HLS playlists of those
had no `#EXT-X-KEY` or DRM signalling in the master playlist, and they play in Kodi through inputstream.adaptive, so the
add-on does not block on this flag. A protected stream that really is encrypted will fail in Kodi.

## Kodi behaviour

- Menu entries use `getVideoInfoTag()` (Kodi 20+) for title, plot, duration and media type.
- Lists set their content type (`episodes`, `tvshows`, `videos`) so skins can pick a suitable view. Kodi plugins cannot
  add a sidebar of their own; search and settings are in the item context menu.
- Kodi marks a played item as watched once most of it has played. Live channels are given media type `video`, a play
  count of 0 and `IsLive=true`, and this stops them being marked as watched.
- A `RunPlugin` action in the settings (the fetch button) runs without a directory, so it handles its own errors and
  does not call `endOfDirectory`.

## Verified

Tried in Kodi 21.3 on Linux with inputstream.adaptive 21.5.22:

- browsing the main menu, categories, sections and series;
- search;
- playback of on-demand programmes and live TV channels;
- the credentials button.

## Not verified

- other platforms (LibreELEC, Android, other desktops) and codecs;
- subtitles and alternate audio tracks, although subtitle URLs are passed on when the preview has them;
- resume behaviour;
- genuinely DRM-protected programmes and content that is restricted to a region or account;
- the long-term availability of these interfaces and the credential locations.

## References

- [Yle developer documentation](https://developer.yle.fi/en/api/index.html)
- [Kodi inputstream.adaptive integration](https://github.com/xbmc/inputstream.adaptive/wiki/Integration)
- [Kodi inputstream.adaptive installation guide](https://github.com/xbmc/inputstream.adaptive/wiki/How-to-install-and-get-updates)
