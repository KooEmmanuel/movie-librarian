# Plex

Default port 32400. Identity (no auth): `curl -s http://HOST:32400/identity`.
Everything else needs a token: `?X-Plex-Token=...` or header `X-Plex-Token`.

**Token:** the user gets it by opening any item in the Plex web app → ⋯ → Get Info →
View XML, and copying `X-Plex-Token=` from the URL. Or from the server:
`grep -o 'PlexOnlineToken="[^"]*"' "<plex data dir>/Preferences.xml"`. Store it as
`server.api_key` in the profile (same field, different meaning).

**Install (Docker):** `assets/docker-compose.plex.yml`. Needs a claim token from
`https://www.plex.tv/claim` (valid 4 minutes) in `PLEX_CLAIM` on first start so the
server attaches to the user's account. Image `plexinc/pms-docker` or
`lscr.io/linuxserver/plex`; both arm64-capable. `network_mode: host` is strongly
preferred for Plex (discovery and remote access work better).

**Libraries:** `curl -s "http://HOST:32400/library/sections?X-Plex-Token=T"` lists
sections with `key` (section id) and `Location path`. Put the movies section id in
`server.plex_section_id`. Creating a library via API is awkward; have the user add
"Movies" pointing at the container path in the web UI.

**Existing titles:**
`curl -s "http://HOST:32400/library/sections/<id>/all?X-Plex-Token=T" | grep -o 'title="[^"]*" [^>]*year="[0-9]*"'`
(XML; add `-H 'Accept: application/json'` for JSON).

**Refresh:** `curl -s "http://HOST:32400/library/sections/<id>/refresh?X-Plex-Token=T"`.

**Naming:** identical to Jellyfin: `Title (Year)/Title (Year).ext`. Force a match with
`{tmdb-NNN}` or `{imdb-ttNNN}` in the folder name (curly braces, not square).

**Caveat to mention once:** hardware transcoding and some mobile features need Plex Pass.
If the user is cost-sensitive or privacy-minded, Jellyfin avoids all of that.
