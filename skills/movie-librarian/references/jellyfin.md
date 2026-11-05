# Jellyfin

## Contents
1. Detect and connect
2. Install with Docker
3. First-run wizard and API key
4. Library and file naming
5. Refresh and verify
6. Troubleshooting

## 1. Detect and connect

Default port 8096 (HTTP), 8920 (HTTPS). Public info endpoint needs no auth:
`curl -s http://HOST:8096/System/Info/Public` → `{"ServerName","Version","StartupWizardCompleted",...}`.
`scripts/media_api.py ping --url http://HOST:8096` prints that.

Auth for everything else: header `X-Emby-Token: <api key>` (Jellyfin kept the Emby header
names). API keys are created in Dashboard → API Keys, or by `media_api.py create-key`
(which logs in with a username/password and mints one). Full API reference is served by
the instance itself at `http://HOST:8096/api-docs/swagger/index.html`; check it when an
endpoint in this doc 404s on an unusual version.

## 2. Install with Docker

Ask these before writing anything, then show the compose file and the exact commands:

- Config folder (persistent; default `~/jellyfin/config`), cache folder (`~/jellyfin/cache`).
- Media root (default `~/media` or an existing drive like `/mnt/<disk>/media`). Movies go in
  `<media>/movies`. Create it now so the library path exists on first scan.
- Port (8096 unless taken; `ss -ltn | grep 8096`).
- Timezone (`cat /etc/timezone` or `timedatectl`).
- Whether a GPU/VAAPI device exists worth passing (`ls /dev/dri`). On a Raspberry Pi 5
  there is no usable hardware transcoder for Jellyfin; leave it out and let clients
  direct-play, which is what the Archive's h.264 mp4s do anyway.

Template: `assets/docker-compose.jellyfin.yml`. Copy to `~/jellyfin/docker-compose.yml`,
substitute paths, UID/GID (`id -u`, `id -g`) and TZ, then:

```bash
mkdir -p ~/jellyfin/{config,cache} <media>/movies
cd ~/jellyfin && docker compose up -d
sleep 10 && curl -s http://localhost:8096/System/Info/Public
```

If the host runs a management layer (Coolify, Portainer, Unraid, CasaOS, TrueNAS), prefer
deploying through it so the user sees the service where they expect; the compose content
is the same. Where a managed container already exists, `detect_server.sh` prints its
mounts and `managed_by`, which tells you the host movies path (left side of the `->`)
without asking; just confirm it with the user. If Coolify is present (`docker ps | grep coolify`), suggest a "Docker Compose"
resource in Coolify and paste the same file, or run compose directly if they'd rather.

Image: `jellyfin/jellyfin:latest` (official, multi-arch, works on arm64). The
`lscr.io/linuxserver/jellyfin` image is fine too and uses `PUID`/`PGID` env instead of `user:`.

Network: `network_mode: host` gives DLNA discovery and simpler client auto-detection on the
LAN. Port mapping (`8096:8096`) is cleaner on a server that already has many containers.
Pick host mode for a dedicated Pi, port mapping otherwise.

## 3. First-run wizard and API key

A fresh instance returns `StartupWizardCompleted: false`. Two ways:

- **User does it:** they open `http://HOST:8096`, pick a language, create an admin user,
  add a Movies library pointing at the *container* path (e.g. `/media/movies`), finish.
- **You do it:** `media_api.py setup-wizard --url http://HOST:8096 --username NAME --password PASS --movies-path /media/movies`.
  Ask the user for the password they want rather than inventing one, and don't echo it back.
  Then `media_api.py create-key --url ... --username NAME --password PASS` prints a key.

Paths: the library path is what the *server process* sees. In Docker that is the right-hand
side of the volume mapping (`/media`), while `library.movies_path` in the profile is the
left-hand side (`/mnt/disk/media/movies`), because the download runs on the host.

## 4. Library and file naming

Jellyfin matches movies by folder/file name and year, then looks up TheMovieDB/OMDb:

```
movies/
  Detour (1945)/
    Detour (1945).mp4
  The Stranger (1946)/
    The Stranger (1946).mp4
```

- One folder per film. Extras (trailers, featurettes) go in subfolders named `extras`.
- Add `[tmdbid-NNN]` or `[imdbid-ttNNN]` to the folder name to force a match when the title
  is ambiguous (many public-domain films share titles: *The Stranger*, *Quicksand*, *Scrooge*).
- Keep the extension the Archive gave; don't remux.
- `.nfo` files are optional; Jellyfin will fetch metadata itself.
- Files must be readable by the server's UID. After a download: `ls -ln <file>`; if owned by
  root or an unexpected user, `chown` to match the `user:` in compose.

Jellyfin's own naming doc: `https://jellyfin.org/docs/general/server/media/movies`.

## 5. Refresh and verify

`media_api.py refresh` posts `/Library/Refresh` (full scan). Real-time monitoring is on by
default when the library was created through the API here, so files usually appear within
a minute anyway. Verify: `media_api.py existing --since-minutes 10` lists what was just
added. A title that shows the folder name with no artwork was not matched; fix the year
or add a `[tmdbid-...]` tag and rescan.

## 6. Troubleshooting

- Container exits immediately with `insufficient free space ... Required: 2GiB` (10.11+):
  the config volume must have 2 GiB free. Never put `/config` on tmpfs or a nearly full disk.
- Container shows `Exited (255)` after a reboot and never came back: `docker start <name>`
  (or redeploy from Coolify/Portainer). Check `restart:` is `unless-stopped`; a container
  that was *stopped* before the reboot stays stopped by design.
- Detect script found the server but `localhost:8096` refuses: the compose file binds a
  specific LAN IP (`192.168.x.x:8096:8096`). Use that IP in `server.url`.

- `ping` works but `existing` returns HTTP 401: the key is wrong or belongs to another
  server. Mint a new one.
- Library path "not found" when adding via API: the path must exist *inside the container*.
  `docker exec <name> ls /media/movies`.
- Movies appear but no posters on a Pi behind AdGuard/Pi-hole: metadata providers are
  being blocked; whitelist `api.themoviedb.org` and `image.tmdb.org`.
- Playback stutters: it's transcoding. Check Dashboard → Playback; with Archive mp4s
  (h.264/AAC) direct play should work; make sure the client isn't forcing a lower bitrate.
- Jellyfin in Docker can't see a USB drive mounted after start: restart the container
  after mounting, or add the mount to fstab so it is there before Docker.
