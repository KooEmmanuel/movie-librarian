#!/usr/bin/env python3
"""Unattended run driven entirely by profile.json. Meant for cron / systemd timers.

  autorun.py            # do a run
  autorun.py --dry-run  # show what it would download
  autorun.py --limit 1  # override run.per_run

Reads profile.json, searches each entry in taste.searches, merges candidates by
downloads, drops anything in history or already in the library, applies the sanity gate
(year/licence/keyword rules from the profile), downloads up to run.per_run within
run.max_gb_per_run, then refreshes the library. Appends to runs.log in the profile folder.
"""
import argparse, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"


def home():
    return os.environ.get("MOVIE_LIBRARIAN_HOME") or os.path.expanduser("~/.config/movie-librarian")


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(os.path.join(home(), "runs.log"), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sh(args, **kw):
    return subprocess.run(args, text=True, capture_output=True, **kw)


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def library_titles(prof):
    """Set of normalised 'title year' strings already present."""
    srv = prof.get("server", {}); lib = prof.get("library", {})
    titles = set()
    if srv.get("type") in ("jellyfin", "emby") and srv.get("url"):
        r = sh([PY, os.path.join(HERE, "media_api.py"), "existing"])
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                titles.add(norm(line))
    path = lib.get("movies_path")
    remote = srv.get("ssh_host") if lib.get("remote") else None
    if path:
        if remote:
            r = sh(["ssh", "-o", "BatchMode=yes", remote, f"ls -1 {path!r} 2>/dev/null"])
            names = r.stdout.splitlines() if r.returncode == 0 else []
        elif os.path.isdir(path):
            names = os.listdir(path)
        else:
            names = []
        for n in names:
            titles.add(norm(n))
    return titles


def gate(doc, rules):
    """Return a reason string if the item should be skipped, else None."""
    title = (doc.get("title") or "").lower()
    year = None
    try:
        year = int(str(doc.get("year"))[:4])
    except (TypeError, ValueError):
        pass
    lic = (doc.get("licenseurl") or "").lower()
    free_lic = any(k in lic for k in ("creativecommons", "publicdomain", "cc0"))
    if year and year > rules.get("pd_year_max", 1930) and not free_lic and year > rules.get("trust_year_max", 1965):
        return f"year {year} with no free licence"
    for kw in rules.get("skip_keywords", []):
        if kw.lower() in title:
            return f"title contains '{kw}'"
    if doc.get("downloads", 0) < rules.get("min_downloads", 0):
        return "too few downloads to trust"
    rt = doc.get("runtime")
    if rt and rules.get("min_runtime_min"):
        m = re.findall(r"\d+", str(rt))
        if m:
            mins = int(m[0]) * 60 + int(m[1]) if len(m) >= 2 and ":" in str(rt) else int(m[0])
            if mins < rules["min_runtime_min"]:
                return f"runtime {rt} below minimum"
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()

    pp = os.path.join(home(), "profile.json")
    if not os.path.exists(pp):
        sys.exit(f"no profile at {pp}; run the setup interview first")
    prof = json.load(open(pp, encoding="utf-8"))
    srv, lib, taste, run = prof.get("server", {}), prof.get("library", {}), prof.get("taste", {}), prof.get("run", {})
    per_run = a.limit or run.get("per_run", 3)
    cap_bytes = float(run.get("max_gb_per_run", 6)) * (1 << 30)
    rules = taste.get("rules", {})
    dest = lib.get("movies_path")
    remote = srv.get("ssh_host") if lib.get("remote") else None
    log(f"run start per_run={per_run} cap={run.get('max_gb_per_run', 6)}GB dest={dest} remote={remote or '-'}")

    if dest and not remote and os.path.isdir(dest):
        du = shutil.disk_usage(dest)
        if du.used / du.total > 0.9:
            log("abort: destination over 90% full"); sys.exit(2)

    have = library_titles(prof)
    seen = {}
    for s in taste.get("searches", []):
        cmd = [PY, os.path.join(HERE, "ia_search.py"), "--exclude-history", "--rows", str(s.get("rows", 30))]
        for c in s.get("collections", []): cmd += ["--collection", c]
        for sub in s.get("subjects", []): cmd += ["--subject", sub]
        if s.get("query"): cmd += ["--query", s["query"]]
        if s.get("year_from"): cmd += ["--year-from", str(s["year_from"])]
        if s.get("year_to"): cmd += ["--year-to", str(s["year_to"])]
        if rules.get("min_downloads"): cmd += ["--min-downloads", str(rules["min_downloads"])]
        r = sh(cmd)
        if r.returncode != 0:
            log(f"search failed: {r.stderr.strip()[:200]}"); continue
        for d in json.loads(r.stdout)["results"]:
            seen.setdefault(d["identifier"], d)
    log(f"candidates: {len(seen)} from {len(taste.get('searches', []))} searches; library has {len(have)} titles")

    picked, spent, skipped = [], 0, []
    for d in sorted(seen.values(), key=lambda x: -x.get("downloads", 0)):
        if len(picked) >= per_run:
            break
        why = gate(d, rules)
        if why:
            skipped.append((d["identifier"], why)); continue
        key = norm(f"{d.get('title')} {d.get('year') or ''}")
        if key in have or norm(d.get("title")) in {re.sub(r"\s\d{4}$", "", h) for h in have}:
            skipped.append((d["identifier"], "already in library")); continue
        plan = sh([PY, os.path.join(HERE, "ia_download.py"), d["identifier"], "--dry-run",
                   "--min-height", str(rules.get("min_height", 0))])
        if plan.returncode != 0:
            skipped.append((d["identifier"], "no usable video file")); continue
        p = json.loads(plan.stdout)
        if spent + p["pick"]["size"] > cap_bytes:
            skipped.append((d["identifier"], f"would exceed size cap ({p['size_human']})")); continue
        picked.append(p); spent += p["pick"]["size"]

    for ident, why in skipped[:25]:
        log(f"skip {ident}: {why}")
    if not picked:
        log("nothing new passed the filters"); return
    for p in picked:
        log(f"{'would download' if a.dry_run else 'downloading'} {p['label']} {p['size_human']} <- {p['identifier']}")
    if a.dry_run:
        return

    ok = 0
    for p in picked:
        cmd = [PY, os.path.join(HERE, "ia_download.py"), p["identifier"], "--dest", dest]
        if remote: cmd += ["--remote", remote]
        r = subprocess.run(cmd, text=True, capture_output=True)
        if r.returncode == 0:
            ok += 1; log(f"ok {p['label']}")
        else:
            log(f"failed {p['label']} exit={r.returncode} {r.stderr.strip()[-300:]}")

    if ok and srv.get("type") in ("jellyfin", "emby"):
        r = sh([PY, os.path.join(HERE, "media_api.py"), "refresh"])
        log("refresh: " + (r.stdout.strip() or r.stderr.strip()))
    elif ok and srv.get("type") == "plex" and srv.get("url") and srv.get("api_key"):
        sec = srv.get("plex_section_id", "")
        r = sh(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"{srv['url']}/library/sections/{sec}/refresh?X-Plex-Token={srv['api_key']}"])
        log(f"plex refresh http {r.stdout}")
    log(f"run done: {ok}/{len(picked)} downloaded")


if __name__ == "__main__":
    main()
