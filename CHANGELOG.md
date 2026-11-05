# Changelog

## Unreleased

- `media_api.py existing --since-minutes` now filters on DateCreated client-side; after a full scan the
  server-side last-saved filter returned the whole library. Found on the first real run.

## 0.1.0 (2026-11-05)

First public release.

- Setup interview: detect Jellyfin/Plex/Emby/Kodi (running or stopped, local or remote), connect, taste profile, manual vs scheduled.
- Jellyfin install via Docker Compose; first-run wizard and API key creation through the API (tested on Jellyfin 10.11 and 12.4).
- Internet Archive search and download with resume, MD5 verification, media-server naming, optional `[imdbid-...]` tags.
- Sanity gate for legality: curated collections, year/licence rule, scene-release keyword filter, known-copyrighted-title check.
- Unattended runner for cron / systemd timers with history, size caps, duplicate detection and library refresh.
- Reference docs for Plex, Emby, Kodi, remote servers over SSH, and scheduling options.
- Three eval cases in the `claude plugin eval` layout.
