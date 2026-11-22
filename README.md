# Yle Arenan for Kodi

An unofficial Kodi add-on for Yle Arenan, the Swedish-language service. Finnish Yle Areena is also available through the
content language setting.

## Status

The add-on is experimental and targets Kodi 21 and newer. Live Yle integration and Kodi playback are not yet fully
verified. It includes:

- a Kodi plug-in entry point and stable `plugin://` navigation URLs;
- Swedish Yle Arenan browsing and search by default, with Finnish Yle Areena available in settings;
- TV-page sections discovered from the structured `__NEXT_DATA__` payload;
- navigation from supported catalogue sections to series pages;
- an experimental playback resolver and subtitle hand-off (not yet verified end-to-end);
- Finnish, Swedish, and English interface strings;
- explicit handling for network, malformed-response, unavailable, protected, and configuration errors.

Yle's web/player interfaces are undocumented and can change. Catalogue lists and search require valid client application
credentials, which are not supplied with this add-on. Configure credentials you are authorized to use in Kodi settings;
never commit them or temporary manifest URLs. The player API uses separate application credentials; configure those
separately. Playback is not yet verified. Live TV, account authentication, DRM bypass, and access-control bypass are not
supported.

## Installation

Install the add-on from the packaged ZIP when a release package is produced. Kodi 21 or newer and the
`inputstream.adaptive` add-on are required. The repository's local development environment currently has Kodi 21.3 with
InputStream Adaptive 21.5.22 available through Flatpak.

For local development, run the **Run Yle Areena Kodi plugin** configuration. It copies the add-on into the Flatpak Kodi
profile and launches Kodi in a window. On first discovery, Kodi may leave it disabled: go to **Add-ons > My add-ons >
Video add-ons > Yle Arenan / Areena**, select **Enable**, then open it under **Add-ons > Video add-ons**. Choose
**Content language** in the add-on settings to switch between Swedish (the default) and Finnish.

Open the add-on settings and provide the Yle client ID and client key required by the observed web endpoints. If Yle
changes or restricts those interfaces, the add-on will report the service error rather than treating the content as
playable.

## Development setup

The project uses only Python's standard library at runtime. Development and test dependencies are listed in
`requirements-dev.txt`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
```

Run the tests with:

```sh
.venv/bin/python -m pytest
```

The `xbmc`, `xbmcgui`, `xbmcplugin`, `xbmcaddon`, and `xbmcvfs` modules are supplied by Kodi and are not installable
from PyPI. The service and parser layers are tested outside Kodi; playback and UI behaviour must be tested in Kodi
itself.

### Kodi desktop controls

On Linux/X11, `tools/kodi_control.py` uses `xdotool`, `ffmpeg`, `pgrep`, and the Flatpak development launcher. It
refuses to start another Kodi when one is already running. Commands explicitly target a visible Kodi window, so use
`list` to identify it first:

```sh
python3 tools/kodi_control.py start
python3 tools/kodi_control.py list
python3 tools/kodi_control.py key --window WINDOW_ID down select
python3 tools/kodi_control.py type --window WINDOW_ID 'search text'
python3 tools/kodi_control.py screenshot --window WINDOW_ID --output /tmp/kodi.png
```

Without `--output`, screenshots are saved to a unique temporary path outside the repository. Existing screenshot files
are never overwritten. Run `python3 tools/kodi_control.py --help` for all commands and `key --help` for available keys.
Starting Kodi deploys the current add-on and uses the normal Flatpak profile; restart Kodi to deploy later source
changes.

## Repository layout

- `addon.xml` - Kodi metadata and runtime dependencies.
- `default.py` - Kodi plug-in entry point and UI adapter.
- `yleareena/` - routes, settings, HTTP transport, service logic, models, and response parsers.
- `resources/settings.xml` - client credential and user-agent settings.
- `resources/language/` - English, Finnish, and Swedish strings.
- `tests/` - focused parser, service, and route tests.
- `docs/technical.md` - investigation notes and implementation constraints.

## Security and compatibility

The add-on validates Yle hosts for service requests, uses HTTPS, bounded timeouts, certificate validation, and limited
retries. It resolves temporary media URLs only when playback starts and does not place them in favourites or logs. It
must not bypass DRM, geographic restrictions, authentication, or other access controls.
