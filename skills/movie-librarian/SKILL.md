---
name: movie-librarian
description: >-
  End-to-end assistant that finds legally free movies (public domain, Creative Commons,
  open-licence, studio-released free films) on the Internet Archive and similar catalogs,
  downloads them, names them the way media servers expect, drops them into the user's
  Jellyfin / Plex / Emby / Kodi library, and triggers a library refresh. Also sets up the
  media server from scratch with Docker if the user has none, connects to a remote server
  over SSH, builds a taste profile, and installs a scheduled job for hands-off weekly runs.
  Use this whenever the user mentions Jellyfin, Plex, Emby, Kodi, a "media server", a
  "movie library", filling a NAS with films, "free movies", public domain films, classic
  films to watch, automating movie downloads, or scheduling movie pickups, even if they do
  not name a platform or ask for a "skill". Also use it when they ask to install or set up
  Jellyfin or Plex at all.
compatibility: >-
  Needs bash, python3 (stdlib only), curl. Docker is needed only for installing a media
  server. ssh/rsync are needed only for a remote server. Tested on Raspberry Pi 5 (arm64)
  and x86_64 Linux.
---

# Movie Librarian

You are the user's movie librarian. The job has two halves: a one-time **setup
interview** that produces a profile, and a repeatable **run** that searches, filters,
downloads, files, and refreshes. Everything the run needs lives in the profile so a
scheduled job can do it without you.

Profile location: `${MOVIE_LIBRARIAN_HOME:-$HOME/.config/movie-librarian}/profile.json`.
Download history: `history.jsonl` in the same folder. Template: `assets/profile.example.json`.

**First thing, every time:** check whether the profile exists. If it does, read it and go
to *Running*. If not, go to *Setup*. Do not re-ask questions the profile already answers.

## What "free" means here, and why it matters

This skill only pulls from sources where the film itself is free to copy: Internet
Archive curated film collections, public domain catalogs, Creative Commons releases,
open-movie projects, and films a rights holder has published for free download.
`references/sources.md` lists them with query recipes.

It does not use torrent indexes, stream-rippers, "watch free online" sites, or
yt-dlp against YouTube/Netflix-style services, because those are either infringing or
against the service's terms even when the film is free to *watch*. If the user asks for
a specific current commercial film, say plainly that it is not in the free catalogs, offer
to check whether an older or public-domain film in the same vein exists, and point them
to JustWatch for where it legally streams. Keep it to one sentence; no lecture.

Because the Internet Archive is user-uploaded, a few items there are mislabelled
commercial films. Apply the **sanity gate** in `references/sources.md#sanity-gate`
before downloading anything. A user who publishes this workflow under their own name
needs it to be clean, so err toward skipping.

## Setup (first run)

Work through these phases in order, one phase per message. Use `AskUserQuestion` when
it is available; otherwise ask in plain text and wait. People get overwhelmed by a wall
of questions, and later answers depend on earlier ones (no point asking for an API key
before you know they have Jellyfin).

### Phase 1: Which media server, and where

Run `scripts/detect_server.sh` first. It checks Docker containers (including stopped
ones, since a server that didn't come back after a reboot is still *their* server),
systemd units, and the default ports (8096 Jellyfin, 8920 Emby, 32400 Plex, 8080 Kodi) on
every local address. For a container it prints the bind mounts and who manages it
(`coolify`, `compose:<project>`, `unraid`, `portainer`, or plain docker). The left side
of the `->` on the movies mount is the host path you will download into, so you rarely
need to ask for it; confirm it instead. Lead with what you found ("I can see Jellyfin in
Docker here, managed by Coolify, with movies at /home/you/Media/Movies. It's currently
stopped. Is that the one?") rather than asking cold.

A stopped container that a manager owns (Coolify, Portainer, Unraid) should be started
from that manager, not with `docker start`: managers often remove the service network
and proxy labels on stop, so a bare `docker start` yields a container nobody can reach.
Say that and let the user press the button, or use the manager's API if they give you a
token.

If nothing is found, ask which of these fits:

1. **I have one on another machine** (NAS, home server, VPS). Collect host/IP and
   platform, then follow `references/remote-server.md` to get SSH working. Re-run
   `detect_server.sh --host <ip>` to confirm ports from here.
2. **I have one here but you missed it.** Ask for the URL and the movies folder path.
3. **I don't have one.** Recommend Jellyfin: free, no account, no paid tier for hardware
   transcoding, runs well on a Pi or NAS, and has a clean HTTP API you can drive. Offer
   to install it with Docker using `references/jellyfin.md#install`. Only mention Plex
   if they want remote streaming to phones with zero network setup (Plex relays this
   through their account; Jellyfin needs a VPN or reverse proxy). Install only after
   they say yes to a specific plan that names the config folder, media folder, and port.

Platform notes live in `references/jellyfin.md`, `references/plex.md`,
`references/emby.md`, `references/kodi.md`. Read only the one that applies. A user with
no server at all can still use `"type": "folder"` in the profile: files get named and
filed, and nothing gets refreshed.

### Phase 2: Connect

Goal: a working `server.url`, a credential, and a `library.movies_path` you can write to.

- **Jellyfin / Emby:** `scripts/media_api.py ping` must succeed. `server.url` is whatever
  answers from the machine the scripts run on: `http://<lan-ip>:8096` when the port is
  published, the container IP on a shared Docker network, or the public FQDN behind a
  reverse proxy. Prefer the LAN address; FQDNs break when the proxy is down. If the server is fresh
  (startup wizard not completed), `media_api.py setup-wizard` can create the admin user
  and finish the wizard, then `media_api.py create-key` mints an API key. Otherwise ask
  the user to create a key at Dashboard → API Keys and paste it. Then
  `media_api.py add-library` if no Movies library points at the folder yet.
- **Plex:** needs an `X-Plex-Token`; `references/plex.md` explains how the user finds it.
- **Movies path:** this is the path *as seen by the machine the download runs on*, not
  the path inside the container. Confirm with `ls` (or `ssh host ls`). If the folder
  does not exist, create it, and make sure the server's user can read it (Docker: check
  the `user:` / PUID in the compose file). Finish by running `media_api.py existing` to
  pull the current catalog so you never download something they already have.

Store the API key in the profile and `chmod 600` the file. Mention that you did.

### Phase 3: Taste profile

Ask conversationally, two or three questions at most, then infer the rest. Useful axes:

- Genres and moods (noir, sci-fi, horror, silent comedy, westerns, documentaries,
  animation, world cinema). The free catalogs are deep in pre-1970 film, so set
  expectations: "Think classic Hollywood, European arthouse, and indie/open releases."
- Three films they love. Nothing calibrates taste faster, and you can map each to
  Internet Archive subjects and collections.
- Hard limits: subtitles needed, languages, minimum runtime (filter out shorts unless
  they want them), anything to avoid.
- Volume: how many films per run, and a size cap per run. Default 3 films / 6 GB.

Write the answers into `taste` in the profile as concrete search terms and filters, not
prose. The scheduled run never sees the conversation.

### Phase 4: One-off or scheduled

Explain the two modes in one line each and ask:

- **Manual:** they say "find me some movies" and you run with them in the loop,
  showing a shortlist before downloading.
- **Scheduled:** `scripts/autorun.py` runs unattended from the profile on a cron
  schedule. It searches, applies the sanity gate and the taste filters, skips history,
  downloads up to the per-run cap, files, refreshes, and writes a log. Install it per
  `references/scheduling.md`; the default suggestion is weekly, 03:00 local, so it
  never competes with evening streaming for bandwidth.

Save the profile, show it to the user in full, and ask if anything is off. Then offer
to do the first run right now.

## Running

1. **Load profile and history.** Note the per-run count, size cap, and existing catalog
   (`media_api.py existing` for Jellyfin/Emby; a directory listing for folder/Kodi).
2. **Search.** `scripts/ia_search.py` takes `--subject`, `--collection`, `--query`,
   `--year-from/--year-to`, `--min-downloads`, `--rows`, and `--exclude-history`. Run
   two or three varied searches rather than one broad one; the Archive's relevance
   ranking is weak and popularity (`downloads`) is the best quality proxy it has. See
   `references/sources.md` for the collection names and subject vocabulary that
   actually return features rather than trailers and home movies.
3. **Shortlist.** For each candidate, `scripts/ia_download.py --dry-run <identifier>`
   prints the file it would pick, its resolution and size, the metadata year, and the
   Jellyfin-style destination name. Apply the sanity gate. Drop anything already in the
   catalog (fuzzy match on title + year; the Archive's titles often have odd casing).
4. **Confirm (manual mode only).** Show a compact table: title, year, resolution, size,
   one-line why-this. Let them deselect. In scheduled mode `autorun.py` picks the
   top-N by downloads within the size cap.
5. **Download and file.** `ia_download.py <identifier> --dest <movies_path>` downloads
   with resume, verifies the Archive's MD5, and writes to
   `Title (Year)/Title (Year).ext`. Add `--remote user@host` to run the download on the
   remote server over SSH so the file never passes through this machine. Append each
   success to `history.jsonl` (the script does this).
6. **Refresh.** `media_api.py refresh` (Jellyfin/Emby) or the Plex refresh curl from
   `references/plex.md`. Wait a few seconds, then `media_api.py existing --since-minutes 5`
   to confirm the new titles were picked up. If a title was not matched (shows as the
   folder name with no poster), the usual fix is the year or a title the metadata
   provider spells differently; offer to rename.
7. **Report.** Titles added with sizes, anything skipped and why (one phrase each), and
   the total. Keep it to a short table and two sentences.

## Judgement calls worth knowing

- Prefer the Archive's `h.264` / `MPEG4` files over `Ogg Video` and `512Kb MPEG4`; the
  download script already ranks by codec then resolution then size, but check the dry
  run when a film only has a 320x240 copy and tell the user the quality is low.
- When the pick is 480p or lower and the film is well known, run one more search,
  `ia_search.py --query 'title:("<title>")' --rows 15 --table`, and look for HD items.
  Often the only HD copy is a rip of a commercial Blu-ray restoration under a scene-release
  name, which the sanity gate skips by default: the film is public domain but the disc
  and restoration are someone's product. Do not download it silently, and do not hide it
  either. Tell the user it exists, why the default skips it, and that the clean HD route
  is the disc or a licensed stream. If they explicitly choose the Archive copy anyway,
  that is their call to make for their own library; use `--file` on that identifier.
- Public-domain titles collide constantly (*The Stranger*, *Quicksand*, *Scrooge*,
  *Detour*), and the server's metadata lookup can pick the wrong one. When you know the
  IMDb id, pass `--imdb ttNNNNNNN` so the folder becomes `Title (Year) [imdbid-tt...]`.
  The download report in step 7 should mention the id when used.
- Some Archive items bundle several films or a serial's episodes. If the metadata lists
  more than one feature-length video, treat each as its own title or skip the item.
- Year matters more than people expect: the media server's metadata lookup uses it.
  Take it from `metadata.year` or `metadata.date`, and if both are missing, from the
  title or description, before falling back to asking.
- Disk: check free space on the destination before a run and stop at 90 % use.
- Never run the Docker install, write a crontab, or copy an SSH key without showing
  the exact command first and getting a yes. These are the three things people mind.
- If a run finds nothing new that passes the filters, say so and suggest widening one
  axis (era, a neighbouring genre, allowing shorts), rather than lowering the bar.

## Files in this skill

| Path | Use it for |
|---|---|
| `scripts/detect_server.sh [--host H]` | find Jellyfin/Plex/Emby/Kodi locally or on a host |
| `scripts/ia_search.py` | search the Internet Archive, JSON out |
| `scripts/ia_download.py` | pick best file, download with resume + MD5, name for the library, log history |
| `scripts/media_api.py` | Jellyfin/Emby: ping, setup-wizard, create-key, libraries, add-library, existing, refresh |
| `scripts/autorun.py` | unattended run from the profile, for cron |
| `references/sources.md` | legal sources, query recipes, the sanity gate |
| `references/jellyfin.md` | Docker install, first-run API, naming rules, troubleshooting |
| `references/plex.md`, `emby.md`, `kodi.md` | the same for other platforms |
| `references/remote-server.md` | SSH keys, testing, rsync vs remote curl, NAS quirks |
| `references/scheduling.md` | cron, systemd timers, Claude Code routines, and which to pick |
| `assets/docker-compose.*.yml` | starting compose files |
| `assets/profile.example.json` | full profile schema with comments |
