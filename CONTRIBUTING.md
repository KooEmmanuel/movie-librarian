# Contributing

Issues and pull requests are welcome. A few ground rules keep the project useful to people
who run it under their own name:

- **Sources stay legal.** Pull requests that add torrent indexes, stream-rippers, or
  downloading from services whose terms forbid it will be closed. New sources need a clear
  licence story (public domain, Creative Commons, or the rights holder's own free release).
- **Scripts stay dependency-free.** Everything under `skills/movie-librarian/scripts` is
  Python standard library plus `curl`/`ssh`, so it runs on a stock Raspberry Pi or NAS.
- **Test before you send.** `python3 -m py_compile skills/movie-librarian/scripts/*.py`,
  `bash -n skills/movie-librarian/scripts/detect_server.sh`, and if you have Claude Code,
  `cd skills/movie-librarian && claude plugin eval . --allow-tools Write,Edit,Bash --scaffold`.
- **Explain the why in SKILL.md.** The skill is read by a model; a sentence of reasoning
  beats a capitalised MUST.
