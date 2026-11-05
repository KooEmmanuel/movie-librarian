#!/usr/bin/env python3
"""Pick the best video file from an Internet Archive item and download it, named for a
media server. Stdlib only.

  ia_download.py IDENTIFIER --dest /srv/media/movies            # download locally
  ia_download.py IDENTIFIER --dest /media/movies --remote nas   # run curl on 'nas' over ssh
  ia_download.py IDENTIFIER --dry-run                           # just show the plan
  ia_download.py IDENTIFIER --dest ... --title "Detour" --year 1945   # override metadata
  ia_download.py IDENTIFIER --dest ... --imdb tt0037638               # pin the match: "Detour (1945) [imdbid-tt0037638]"

Destination layout:  <dest>/<Title (Year)>/<Title (Year)>.<ext>
Verifies the MD5 the Archive publishes. Appends a line to history.jsonl on success.
Exit codes: 0 ok, 1 error, 3 skipped (already present / nothing suitable / over size cap).
"""
import argparse, hashlib, json, os, re, shlex, subprocess, sys, time, urllib.parse, urllib.request

UA = "movie-librarian/1.0"
CODEC_RANK = {"h.264": 0, "matroska": 0, "mpeg4": 1, "h.264 ia": 1, "512kb mpeg4": 3, "ogg video": 4, "mpeg2": 2, "windows media": 5, "quicktime": 2}
VIDEO_EXT = (".mp4", ".mkv", ".m4v", ".avi", ".ogv", ".mpg", ".mpeg", ".mov", ".webm")


def home():
    return os.environ.get("MOVIE_LIBRARIAN_HOME") or os.path.expanduser("~/.config/movie-librarian")


def fetch_meta(identifier):
    req = urllib.request.Request(f"https://archive.org/metadata/{identifier}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def clean_title(t):
    t = re.sub(r"\s*\(\d{4}\)\s*$", "", t or "").strip()
    t = re.sub(r"[\\/:*?\"<>|]", "", t)        # characters most filesystems reject
    t = re.sub(r"\s+", " ", t)
    return t[:120].strip(" .")


def guess_year(md):
    for k in ("year", "date"):
        v = md.get(k)
        if isinstance(v, list):
            v = v[0]
        if v:
            m = re.search(r"(18|19|20)\d{2}", str(v))
            if m:
                return m.group(0)
    for k in ("title", "description"):
        v = md.get(k)
        if isinstance(v, list):
            v = " ".join(v)
        m = re.search(r"\b(18|19|20)\d{2}\b", str(v or ""))
        if m:
            return m.group(0)
    return None


def rank_files(files):
    cands = []
    for f in files:
        name = f.get("name", "")
        if not name.lower().endswith(VIDEO_EXT):
            continue
        if f.get("source") == "derivative" and "512kb" in name.lower():
            pass  # keep but ranked low
        fmt = (f.get("format") or "").lower()
        rank = CODEC_RANK.get(fmt, 2)
        if name.lower().endswith(".ogv"):
            rank = max(rank, 4)
        try:
            w = int(f.get("width") or 0); h = int(f.get("height") or 0)
        except ValueError:
            w = h = 0
        size = int(f.get("size") or 0)
        try:
            length = float(f.get("length") or 0)
        except ValueError:
            length = 0.0
        cands.append({"name": name, "format": f.get("format"), "rank": rank, "width": w, "height": h,
                      "size": size, "md5": f.get("md5"), "length_s": length})
    # best: lowest codec rank, then largest height, then largest size
    cands.sort(key=lambda c: (c["rank"], -c["height"], -c["size"]))
    return cands


def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.2f} TB"


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_ssh(host, cmd, check=True):
    return subprocess.run(["ssh", "-o", "BatchMode=yes", host, cmd], text=True, capture_output=True, check=check)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("identifier")
    ap.add_argument("--dest", help="movies root (on the remote host if --remote)")
    ap.add_argument("--remote", help="ssh host alias or user@host; download happens there with curl")
    ap.add_argument("--title"); ap.add_argument("--year")
    ap.add_argument("--imdb", help="IMDb id like tt0037638; appended as [imdbid-...] so the server matches the right film")
    ap.add_argument("--tmdb", help="TMDb id; appended as [tmdbid-...]")
    ap.add_argument("--max-gb", type=float, default=0, help="skip if the chosen file is larger")
    ap.add_argument("--min-height", type=int, default=0, help="skip files shorter than this many pixels")
    ap.add_argument("--file", help="force a specific file name from the item")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-history", action="store_true")
    a = ap.parse_args()

    try:
        meta = fetch_meta(a.identifier)
    except Exception as e:  # noqa: BLE001
        print(f"error: cannot fetch metadata for {a.identifier}: {e}", file=sys.stderr); sys.exit(1)
    md = meta.get("metadata") or {}
    if not md:
        print(f"error: {a.identifier} has no metadata (item removed or dark)", file=sys.stderr); sys.exit(1)

    title = clean_title(a.title or (md.get("title")[0] if isinstance(md.get("title"), list) else md.get("title")))
    year = a.year or guess_year(md)
    label = f"{title} ({year})" if year else title
    tag = f" [imdbid-{a.imdb}]" if a.imdb else (f" [tmdbid-{a.tmdb}]" if a.tmdb else "")
    fs_label = label + tag          # folder and file name; the id tag pins metadata matching

    cands = rank_files(meta.get("files", []))
    if a.file:
        cands = [c for c in cands if c["name"] == a.file]
    if a.min_height:
        cands = [c for c in cands if c["height"] >= a.min_height or c["height"] == 0]
    plan = {
        "identifier": a.identifier, "title": title, "year": year, "label": label,
        "license": md.get("licenseurl"), "collection": md.get("collection"),
        "candidates": [{k: c[k] for k in ("name", "format", "width", "height", "size")} for c in cands[:6]],
    }
    if not cands:
        plan["status"] = "skipped"; plan["reason"] = "no video file in item"
        print(json.dumps(plan, indent=1)); sys.exit(3)
    pick = cands[0]
    ext = os.path.splitext(pick["name"])[1].lower()
    plan.update({"pick": pick, "size_human": human(pick["size"]),
                 "relative_path": f"{fs_label}/{fs_label}{ext}",
                 "url": f"https://archive.org/download/{a.identifier}/{urllib.parse.quote(pick['name'])}"})
    if a.max_gb and pick["size"] > a.max_gb * (1 << 30):
        plan["status"] = "skipped"; plan["reason"] = f"{human(pick['size'])} exceeds cap {a.max_gb} GB"
        print(json.dumps(plan, indent=1)); sys.exit(3)
    if pick["height"] and pick["height"] < 360:
        plan["warning"] = f"low resolution: {pick['width']}x{pick['height']}"
    if a.dry_run or not a.dest:
        plan["status"] = "dry-run"
        print(json.dumps(plan, indent=1)); return

    rel_dir = fs_label
    final_name = f"{fs_label}{ext}"
    started = time.time()

    if a.remote:
        ddir = f"{a.dest.rstrip('/')}/{rel_dir}"
        q = shlex.quote
        check = run_ssh(a.remote, f"test -e {q(ddir + '/' + final_name)} && echo EXISTS || echo OK")
        if "EXISTS" in check.stdout:
            plan["status"] = "skipped"; plan["reason"] = "file already exists on remote"
            print(json.dumps(plan, indent=1)); sys.exit(3)
        cmd = (f"mkdir -p {q(ddir)} && cd {q(ddir)} && "
               f"curl -L --fail --retry 5 --retry-delay 10 -C - -A {q(UA)} -o {q(final_name + '.part')} {q(plan['url'])} && "
               f"mv {q(final_name + '.part')} {q(final_name)} && md5sum {q(final_name)}")
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", a.remote, cmd], text=True, capture_output=True)
        if r.returncode != 0:
            print(r.stderr[-2000:], file=sys.stderr)
            print(f"error: remote download failed (exit {r.returncode})", file=sys.stderr); sys.exit(1)
        got = r.stdout.split()[0] if r.stdout.strip() else ""
        final_path = f"{a.remote}:{ddir}/{final_name}"
    else:
        ddir = os.path.join(a.dest, rel_dir)
        final_path = os.path.join(ddir, final_name)
        if os.path.exists(final_path):
            plan["status"] = "skipped"; plan["reason"] = "file already exists"
            print(json.dumps(plan, indent=1)); sys.exit(3)
        os.makedirs(ddir, exist_ok=True)
        part = final_path + ".part"
        cmd = ["curl", "-L", "--fail", "--retry", "5", "--retry-delay", "10", "-C", "-", "-A", UA,
               "--progress-bar", "-o", part, plan["url"]]
        r = subprocess.run(cmd)
        if r.returncode != 0:
            print(f"error: curl exit {r.returncode}; partial kept at {part} for resume", file=sys.stderr); sys.exit(1)
        os.replace(part, final_path)
        got = md5_of(final_path)

    if pick["md5"] and got and got != pick["md5"]:
        plan["status"] = "error"; plan["reason"] = f"md5 mismatch: expected {pick['md5']} got {got}"
        print(json.dumps(plan, indent=1)); sys.exit(1)

    plan.update({"status": "ok", "path": final_path, "md5_verified": bool(pick["md5"]),
                 "seconds": round(time.time() - started)})
    if not a.no_history:
        os.makedirs(home(), exist_ok=True)
        with open(os.path.join(home(), "history.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "identifier": a.identifier,
                                 "title": title, "year": year, "path": final_path, "size": pick["size"]}) + "\n")
    print(json.dumps(plan, indent=1))


if __name__ == "__main__":
    main()
