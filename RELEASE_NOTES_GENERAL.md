**Rootnote** — phone speaker virtual bass · unofficial RootlessJamesDSP fork
(폰 스피커 가상 저음 · RootlessJamesDSP 기반 비공식 포크)

Beta for Android 10+ (arm64). Not made or supported by the RootlessJamesDSP/JamesDSP developers. GPL-3.0, no warranty.
The corresponding source is the tagged commit; `source-*.tar.gz` below contains it with the `libjamesdsp` submodule.

- Setup needs Shizuku or ADB once (the app shows the exact commands for its package on first start).
- Android 15+: turn on "Disable screen share protections" in Developer options.
- Apps that block audio capture (Spotify, Chrome, SoundCloud, ...) play unprocessed.
- Measured settings exist only for the Galaxy S26 Ultra; other phones start with conservative neutral settings.
- Privacy: only settings are stored; no song titles, no recordings, nothing sent (see PRIVACY.md).

Verify the download with the `.sha256` file.
