# Scheduling unattended runs

`scripts/autorun.py` does a complete run from the profile with no model involved:
search, gate, dedupe, download, refresh, log. Schedule *that*. Bringing Claude into the
scheduled job is optional and costs tokens on every run; the taste profile already
encodes the judgement.

Pick the mechanism by where the profile lives:

## cron on this machine (default)

```bash
# weekly, Sunday 03:00; adjust. `crontab -e` is interactive, so append non-interactively:
( crontab -l 2>/dev/null; echo "0 3 * * 0 /usr/bin/python3 $HOME/.claude/skills/movie-librarian/scripts/autorun.py >> $HOME/.config/movie-librarian/cron.log 2>&1" ) | crontab -
crontab -l | grep autorun   # show the user the installed line
```

Show the exact line before installing it. Use absolute paths (cron has a minimal PATH).
If `MOVIE_LIBRARIAN_HOME` is customised, prefix the command with `MOVIE_LIBRARIAN_HOME=...`.
A Pi that is sometimes off: add `@reboot sleep 300 && ...` as well, or use the systemd
timer below with `Persistent=true` so missed runs catch up.

## systemd user timer (catches up after downtime)

`~/.config/systemd/user/movie-librarian.service`:
```ini
[Unit]
Description=Movie librarian run
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 %h/.claude/skills/movie-librarian/scripts/autorun.py
```
`~/.config/systemd/user/movie-librarian.timer`:
```ini
[Unit]
Description=Weekly movie pickup
[Timer]
OnCalendar=Sun *-*-* 03:00:00
Persistent=true
RandomizedDelaySec=15m
[Install]
WantedBy=timers.target
```
```bash
systemctl --user daemon-reload && systemctl --user enable --now movie-librarian.timer
loginctl enable-linger $USER     # so user timers run when not logged in
systemctl --user list-timers | grep movie
```

## Claude Code scheduled routines (cloud)

The `/schedule` skill creates cloud-hosted routines. They run in a sandbox that cannot
see a home LAN, so they only fit when the media server has a public SSH endpoint or the
user wants Claude to *curate* (pick titles, write a shortlist to a doc or email) while a
local cron does the downloading. For a home Pi/NAS, prefer cron or the systemd timer.

## Claude-in-the-loop locally

If the user wants the model's judgement on every run (e.g. "surprise me with a themed
pick"), cron can call Claude Code headless:
```
0 3 * * 0 cd $HOME && claude -p "Use the movie-librarian skill to do a scheduled run. Be brief." --allowedTools Bash,Read >> $HOME/.config/movie-librarian/cron.log 2>&1
```
This needs a logged-in `claude` CLI and will spend tokens weekly; say so.

## Logs and health

`runs.log` and `cron.log` in the profile folder. `tail -20 ~/.config/movie-librarian/runs.log`
shows the last run. Offer a "dry run now" (`autorun.py --dry-run`) right after installing
the schedule so the user sees what next Sunday would fetch.
