# Movie Librarian

A [Claude Code](https://claude.com/claude-code) skill that turns Claude into the librarian for your home
media server. Tell it what you like, and it finds **legally free films** (public domain, Creative Commons,
open-movie projects), downloads them, names them the way Jellyfin / Plex / Emby / Kodi expect, drops them
into your library, and refreshes the server. If you don't have a media server yet, it installs Jellyfin
with Docker for you. If you want it hands-off, it installs a weekly job that keeps the shelves growing.

Runs on anything with `python3`, `bash` and `curl`, including a Raspberry Pi or a NAS. No Python packages
to install.

> **What "free" means here.** Sources are the Internet Archive's curated film collections, public-domain
> catalogs, Creative Commons releases, Blender's open movies and films a rights holder has published for
> free download. The skill will not use torrent indexes, stream-rippers or `yt-dlp` against YouTube-style
> services, and it has a sanity gate that skips mislabelled commercial uploads. That is deliberate: a tool
> you run under your own name has to be clean.

## What it does

```
you:     I want classic movies showing up in my Jellyfin every week without me doing anything.

claude:  I can see Jellyfin in Docker on this machine with movies at /srv/media/movies. Is that the one?
         ... (a few questions: genres, three films you love, how many per week, what time) ...
         Profile saved. Here's what next Sunday would fetch:
           The Stranger (1946)     640x480  544 MB   Orson Welles; if you love The Third Man...
           Scarlet Street (1945)   640x480  604 MB   Fritz Lang's American noir peak
           Detour (1945)           640x480  404 MB   Ulmer's poverty-row masterpiece
         Shall I run it now and install the Sunday 03:00 job?
```

Behind that conversation:

| Phase | What happens |
|---|---|
| **Detect** | Finds Jellyfin/Plex/Emby/Kodi in Docker (running *or* stopped), systemd, or on the default ports of every local address or a remote host. Reads bind mounts so it knows the movies folder without asking. Knows when a container belongs to Coolify/Portainer/Unraid and should be started from there. |
| **Install** (if needed) | Recommends Jellyfin, writes a Docker Compose file from the bundled template, completes the first-run wizard and mints an API key through the API. Plex and Emby templates included. |
| **Connect** | Local path, or a remote server over SSH (walks the user through keys and `~/.ssh/config`). Downloads can run *on* the remote box so files never pass through the controlling machine. |
| **Taste** | Two or three conversational questions become concrete Internet Archive search recipes and filters in a profile file. |
| **Run** | Search → sanity gate → dedupe against the existing library → shortlist (manual mode) or auto-pick (scheduled) → download with resume and MD5 verification → `Title (Year)/Title (Year).ext` → library refresh → short report. |
| **Schedule** | A dependency-free runner (`autorun.py`) driven by the profile, installed as a cron line or systemd timer. No model calls at run time, so the weekly job costs nothing. |

## Install

**As a Claude Code plugin** (recommended):

```
/plugin marketplace add KooEmmanuel/movie-librarian
/plugin install movie-librarian@movie-librarian
```

**Or as a personal skill:**

```bash
git clone https://github.com/KooEmmanuel/movie-librarian ~/projects/movie-librarian
ln -s ~/projects/movie-librarian/skills/movie-librarian ~/.claude/skills/movie-librarian
```

Then start Claude Code and say something like *"set up free classic movies for my Jellyfin"*. The skill
triggers on mentions of Jellyfin, Plex, Emby, Kodi, media servers, movie libraries, public-domain films,
or automating movie downloads.

Requirements: `bash`, `python3` (3.8+, standard library only), `curl`. Docker only if you want it to
install a media server. `ssh`/`rsync` only for a remote server.

## Usage examples

- *"Find me 3 noir films for tonight, don't download yet."*
- *"Grab Detour (1945) from the Internet Archive and file it for Jellyfin."*
- *"My Plex is on my Synology at 192.168.1.20, set this up to pull two westerns a week."*
- *"I don't have a media server. What should I use, and can you install it?"*
- *"Run my movie pickup now."* (uses the saved profile)

## How a run decides what to download

1. **Search** the Archive's curated collections (`feature_films`, `Film_Noir`, `SciFi_Horror`,
   `comedy_films`, `silent_films`, `westerns`, ...) with the profile's subjects, year ranges and
   director queries. Download counts are the quality signal: a noir with 400k downloads is a real
   transfer; one with 300 is probably a bad rip.
2. **Sanity gate** ([details](skills/movie-librarian/references/sources.md#3-sanity-gate)): skip anything
   after 1965 without an explicit CC/PD licence, anything with scene-release tags (`1080p`, `BluRay`,
   `x264`, `YIFY`...), low-download community uploads without a licence, trailers and excerpts, and
   well-known still-copyrighted titles regardless of what the uploader claims.
3. **Dedupe** against the server's catalog (via API) or the movies folder.
4. **Pick the best file** in each item: h.264/MPEG-4 over Ogg, highest resolution, then size.
5. **Download** with resume, verify the Archive's MD5, write `Title (Year)/Title (Year).ext`
   (optionally `[imdbid-tt...]` to pin the metadata match), log to `history.jsonl`.
6. **Refresh** the library and confirm the new titles were matched.

When the only HD copy of a public-domain film is a Blu-ray rip under a scene-release name, the skill
tells the user it exists and why it skipped it, rather than downloading it silently or hiding it.

## The profile

Lives at `~/.config/movie-librarian/profile.json` (override with `MOVIE_LIBRARIAN_HOME`), mode 600
because it holds the server API key. Full annotated example:
[`assets/profile.example.json`](skills/movie-librarian/assets/profile.example.json).

```json
{
  "server":  { "type": "jellyfin", "url": "http://192.168.1.50:8096", "api_key": "...", "ssh_host": null },
  "library": { "movies_path": "/srv/media/movies", "container_path": "/media/movies", "remote": false },
  "taste":   { "searches": [ { "collections": ["Film_Noir"], "subjects": ["noir"], "year_from": 1940, "year_to": 1960 } ],
               "rules": { "trust_year_max": 1965, "min_downloads": 5000, "min_runtime_min": 55, "min_height": 360 } },
  "run":     { "mode": "scheduled", "per_run": 3, "max_gb_per_run": 6, "schedule": "0 3 * * 0" }
}
```

## Scripts

All under [`skills/movie-librarian/scripts`](skills/movie-librarian/scripts). Each prints `--help`.

| Script | Purpose |
|---|---|
| `detect_server.sh [--host H] [--json]` | Find media servers: Docker (incl. stopped, with mounts and manager), systemd, default ports. |
| `ia_search.py` | Internet Archive search → JSON (`--collection`, `--subject`, `--query`, `--year-from/to`, `--min-downloads`, `--exclude-history`, `--table`). |
| `ia_download.py ID --dest DIR [--remote HOST] [--imdb tt...] [--dry-run]` | Pick the best file, download with resume, verify MD5, name for the server, log history. |
| `media_api.py` | Jellyfin/Emby: `ping`, `setup-wizard`, `create-key`, `libraries`, `add-library`, `existing`, `refresh`, `item-count`. |
| `autorun.py [--dry-run] [--limit N]` | Unattended run from the profile, for cron/systemd. |

## Scheduling

`autorun.py` is what gets scheduled. The skill shows the exact line before installing it:

```
0 3 * * 0 /usr/bin/python3 /path/to/skills/movie-librarian/scripts/autorun.py >> ~/.config/movie-librarian/cron.log 2>&1
```

A systemd user timer with `Persistent=true` is documented for machines that are sometimes off. See
[`references/scheduling.md`](skills/movie-librarian/references/scheduling.md).

## Supported platforms

| Server | Detect | Install | API refresh | Notes |
|---|---|---|---|---|
| Jellyfin | yes | Docker Compose | yes (tested 10.11, 12.4) | recommended; wizard + API key automated |
| Emby | yes | Docker Compose | yes (same API family) | |
| Plex | yes | Docker Compose | yes (token + section id) | needs the user's `X-Plex-Token` |
| Kodi | yes | n/a | JSON-RPC scan | it's a player; files land in a folder it reads |
| none / folder | n/a | n/a | n/a | files are named and filed for a future server |

## Testing

The `evals/` folder holds three test cases in the layout `claude plugin eval` reads:

```bash
cd skills/movie-librarian
claude plugin eval . --allow-tools Write,Edit,Bash --scaffold
```

They cover: a shortlist from an existing profile (no downloads), a first-run plan on a machine where
nothing may be changed, and a real download of one named film with checksum verification.

## FAQ

**Why not torrents? Public-domain torrents are legal.** The client and the swarm mix in content you
cannot audit, and the scripts would have to carry a torrent client. Direct HTTPS from curated archives
gives the same films with a provenance trail.

**Everything is 480p.** That is the ceiling for most public-domain prints on the Archive. The skill tells
you when a higher-resolution copy exists and lets you decide. For restorations, buy the disc.

**Can it do TV shows?** Not yet. The Archive's TV holdings are thinner and naming rules differ.

**Does the weekly job spend Claude tokens?** No. `autorun.py` is plain Python driven by the profile.
Claude is involved only in setup and in manual runs where you want a curated shortlist.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version: sources stay legal, scripts stay
dependency-free, explain the why in `SKILL.md`.

## License

MIT. See [LICENSE](LICENSE).
