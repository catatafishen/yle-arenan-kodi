# Yle Arenan for Kodi

An unofficial Kodi add-on for Yle Arenan, the Swedish-language service. Finnish Yle Areena is also available through the
content language setting.

## Status

The add-on is experimental and targets Kodi 21 and newer. Browsing, search and on-demand playback have been tried in
Kodi 21.3 on Linux, including with inputstream.adaptive. Other platforms have not been tested.

What works:

- **Main menu:** live TV channels first, then the genre categories from the website's "Sök och bläddra" menu, then the
  catalogue sections of the TV page. Sections show the thumbnail of their first item and the titles of the first few in
  the plot text.
- **Series:** opening a series shows its episodes directly, with the other lists (such as clips) after them. Lists that
  Yle pages in several requests are merged, and the "Se mer" similar-content lists are left out.
- **Search and settings:** both are in the context menu (long-press or right-click) on any item.
- **Playback:** on-demand programmes and live TV channels (Yle TV1, TV2 and Teema Fem) play through
  inputstream.adaptive. Live channels are marked as live so Kodi does not mark them as watched.
- **Credentials:** a **Fetch credentials from Yle** button in the settings fills in the four credential fields.
- **Languages:** Swedish (the default) and Finnish content, with English, Swedish and Finnish interface strings.
- **Errors:** network, malformed-response, unavailable and configuration problems are shown in a dialog instead of
  failing silently.

Not supported: radio channels, the Direkt "Sport" list, podcasts, account sign-in ("Mina" and favourites), and anything
that needs DRM or other access-control bypass.

Yle's web and player interfaces are undocumented and can change without notice.
See [docs/technical.md](docs/technical.md)
for what has been observed.

## Installation

Download the latest zip from the [releases page](https://github.com/catatafishen/yle-arenan-kodi/releases) and install
it in Kodi with **Add-ons > Install from
zip file**. Kodi 21 or newer and the `inputstream.adaptive` add-on are required.

The add-on needs four credentials to talk to Yle. After installing, open the add-on settings and press **Fetch
credentials from Yle**. They are the same public application keys that Yle's own website gives every browser, read from
the site on your own machine, so you get whatever Yle serves to a browser in your region. They are never part of this
repository. If the button fails, for example because Yle changed its pages, the fields can still be filled in by hand
from the browser's network tab.

Choose **Content language** in the settings to switch between Swedish (the default) and Finnish.

For local development, run the **Run Yle Areena Kodi plugin** configuration. It copies the add-on into the Flatpak Kodi
profile and launches Kodi in a window. On first discovery, Kodi may leave it disabled: go to **Add-ons > My add-ons >
Video add-ons > Yle Arenan / Areena**, select **Enable**, then open it under **Add-ons > Video add-ons**. The
development environment uses Kodi 21.3 with InputStream Adaptive 21.5.22 from Flatpak.

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

## Releases and versioning

Every push to `master` runs the tests and builds the add-on zip. The version is worked out automatically
from [Conventional Commits](https://www.conventionalcommits.org) since the last release tag,
using [semantic versioning](https://semver.org):

| Commit                                                   | Release               |
|----------------------------------------------------------|-----------------------|
| `fix: ...`, `perf: ...`                                  | patch (0.1.0 → 0.1.1) |
| `feat: ...`                                              | minor (0.1.0 → 0.2.0) |
| `feat!: ...`, or a `BREAKING CHANGE:` footer             | major (0.1.0 → 1.0.0) |
| `docs:`, `chore:`, `ci:`, `test:`, `refactor:`, `style:` | no release            |

When a release is due, the workflow tags the commit (`v0.2.0`), publishes a GitHub release with generated notes, and
attaches the zip. The version is stamped into the zip's `addon.xml` only, so `addon.xml` in the repository does not need
editing. Add `[skip-release]` to a commit message to keep it out of the version calculation. Pull requests build the zip
as an artifact but never create a release.

`master` is protected: changes go in through a pull request and the `build` check must pass. Pull requests can only
be merged with "Rebase and merge", which keeps each commit as it is, so every commit message must be a valid
Conventional Commit: the messages decide the version.

## Repository layout

- `addon.xml` - Kodi metadata and runtime dependencies.
- `default.py` - Kodi plug-in entry point and UI adapter.
- `yleareena/` - routes, settings, HTTP transport, service logic, models, response parsers and the credential fetcher.
- `resources/settings.xml` - credential, language and user-agent settings, and the fetch button.
- `resources/language/` - English, Finnish, and Swedish strings.
- `tests/` - parser, service, route, credential and entry-point tests.
- `tools/` - Kodi development launcher and desktop controls.
- `docs/technical.md` - what was observed about Yle's web and player interfaces, and the constraints that follow.
- `AGENTS.md` - rules for automated coding agents working in this repository.

## Security and compatibility

The add-on validates Yle hosts for service requests, uses HTTPS, bounded timeouts, certificate validation, and limited
retries. It resolves temporary media URLs only when playback starts and does not place them in favourites or logs. It
must not bypass DRM, geographic restrictions, authentication, or other access controls.
