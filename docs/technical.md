# Technical investigation

This document records the web and player behaviour observed while investigating a possible Yle Areena Kodi integration. The interfaces described here are undocumented implementation details and may change without notice. The observations are not a guarantee that every programme, platform, or region is supported.

## Investigation scope

The investigation used publicly accessible Yle Areena web pages on 22 November 2026. It did not spoof location, sign in to an account, bypass access controls, or attempt to defeat DRM. Playback in Kodi was not verified.

One globally available on-demand programme produced a player preview containing an HLS master manifest. The manifest request succeeded and exposed multiple bitrate variants, but that only demonstrates that one sample could be resolved; it does not establish general playback support.

## Web page data

Yle Arenan (`arenan.yle.fi`) is the Swedish-language service and Yle Areena (`areena.yle.fi`) is the Finnish-language service. The add-on defaults to Arenan; the content language setting switches the TV and item pages as well as the search API language. The two TV pages have different curated sections, not just translated labels.

Both sites include a `__NEXT_DATA__` JSON object. The structured data observed on series and TV pages included:

- series tabs and programme lists;
- browse categories;
- filters and options;
- pagination metadata;
- programme, clip, series, and package pointers;
- titles, descriptions, and image metadata.

An add-on should parse structured fields and stable identifiers rather than translated tab labels or rendered HTML. Fields may be absent or renamed, so parsing must validate response shapes and report service errors instead of silently treating malformed data as an empty catalogue.

## Observed service endpoints

### Search

```text
https://areena.api.yle.fi/v1/ui/search
```

Observed responses contained a `data` array of cards. Cards included a `pointer` with a type and URI, title, description, and image metadata. Pagination information was also returned.

Pointer types need separate handling. A programme or clip can become a playable item, while a series or package should open another Kodi folder. Search pagination should use the response's pagination data and should not assume that a fixed page size or a translated label remains stable.

### Player preview

```text
https://player.api.yle.fi/v1/preview/{id}.json
```

For the sample programme, availability and metadata were under:

```text
 data.ongoing_ondemand
```

The observed data included an expiring `manifest_url`, audio tracks, and subtitle information. The web player also recognizes states including `pending_ondemand`, `pending_event`, `gone`, `blocked`, `not_allowed`, `not_allowed_channel`, `identification`, and `error`; these are keys under `data`, not necessarily a `state` string. The add-on reports these separately, and rejects unknown response shapes. A separate programme tested in Kodi returned `not_allowed`; the cause of the originally reported episode's failure has not been established. Its public page labels it Finland-only, which is not sufficient by itself to determine why the player refused it.

The manifest URL is temporary. It must be resolved at playback time, never stored in a Kodi favourite, committed to the repository, or written to normal logs.

## Required request details

The web interfaces use client application identifiers or keys. Requests made without the required client information returned HTTP 403 during the investigation. The correct long-term credential strategy is unresolved. Do not copy browser secrets, session cookies, signed URLs, or tokens into source control.

Before implementation, determine whether the intended integration is permitted and maintainable. Yle's developer documentation states that there is no public media API. Any implementation must respect Yle's terms, authentication requirements, geographic restrictions, and content protection. It must not bypass DRM or access controls.

## Proposed Kodi playback flow

1. Browse or search using catalogue data and keep only stable content identifiers in item URLs.
2. When a user selects a playable item, request a fresh player preview.
3. Validate availability and inspect the returned media and protection state.
4. Pass a supported HLS or DASH stream to Kodi's `inputstream.adaptive` when the content and platform allow it.
5. Pass subtitle information to Kodi when supported and expose audio-track choices through the player.
6. Surface a clear error for missing inputstream support, expired links, unavailable content, region restrictions, authentication requirements, protection modes, network failures, and unexpected response formats.

Kodi favourites should contain stable `plugin://` URLs built from content IDs and navigation parameters. They must not contain the temporary manifest URL, request tokens, or list pagination tokens. A favourite should reopen the same folder or item after Kodi restarts, including when cached catalogue data has expired.

## Architecture implications

Keep the service client, response parsing, and playback resolver independent from Kodi UI modules. This makes it possible to test them with saved, redacted response fixtures and mocked HTTP responses. The Kodi layer should be responsible for directory items, localized labels, playback hand-off, notifications, and settings.

Use bounded timeouts, certificate validation, and limited retries only for appropriate transient failures. Cache catalogue metadata for a bounded period, but do not cache signed media URLs. Store settings and local state under Kodi's add-on profile rather than the installation directory, and redact credentials and signed URLs from logs.

The add-on should target Kodi 21 and newer. `inputstream.adaptive` is a platform dependency and must be declared by the add-on rather than bundling platform-specific binaries. Codec, DRM/CDM, subtitle, and inputstream support can vary between LibreELEC, desktop, Android, and other Kodi platforms.

## Verification still required

The following were not established by the investigation and require implementation testing:

- playback of the sample manifest in Kodi;
- playback behaviour across Kodi-supported platforms;
- subtitle and alternate-audio handling;
- resume behaviour;
- protected or DRM-backed programmes;
- region-restricted and account-only content;
- expiry and refresh behaviour for preview and manifest URLs;
- continued availability and permission to use the observed web interfaces.

A test plan should include representative fixtures for successful playback, missing fields, expired content, HTTP errors, protection states, pagination, and each pointer type. End-to-end playback should be tested on actual Kodi devices, not only in a desktop Python environment.

## References

- [Yle developer documentation](https://developer.yle.fi/en/api/index.html)
- [Kodi inputstream.adaptive integration](https://github.com/xbmc/inputstream.adaptive/wiki/Integration)
- [Kodi inputstream.adaptive installation guide](https://github.com/xbmc/inputstream.adaptive/wiki/How-to-install-and-get-updates)
