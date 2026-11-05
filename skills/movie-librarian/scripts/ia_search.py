#!/usr/bin/env python3
"""Search the Internet Archive for free films. Stdlib only.

Examples:
  ia_search.py --collection feature_films --subject noir --rows 20
  ia_search.py --query 'director:(hitchcock)' --year-to 1950
  ia_search.py --subject "science fiction" --min-downloads 20000 --exclude-history

Output: JSON object {query, numFound, results:[{identifier,title,year,downloads,avg_rating,
runtime,licenseurl,collection,subject,description}]} sorted by downloads desc.
Use --table for a human view.
"""
import argparse, json, os, sys, urllib.parse, urllib.request

API = "https://archive.org/advancedsearch.php"
UA = "movie-librarian/1.0 (+https://archive.org/details/feature_films)"


def home():
    return os.environ.get("MOVIE_LIBRARIAN_HOME") or os.path.expanduser("~/.config/movie-librarian")


def history_ids():
    p = os.path.join(home(), "history.jsonl")
    ids = set()
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    ids.add(json.loads(line).get("identifier"))
                except json.JSONDecodeError:
                    pass
    return ids


def build_query(a):
    parts = ["mediatype:movies"]
    if a.collection:
        parts.append("(" + " OR ".join(f"collection:{c}" for c in a.collection) + ")")
    if a.subject:
        parts.append("(" + " OR ".join(f'subject:("{s}")' for s in a.subject) + ")")
    if a.query:
        parts.append(f"({a.query})")
    if a.year_from or a.year_to:
        parts.append(f"year:[{a.year_from or 1890} TO {a.year_to or 2100}]")
    if a.min_downloads:
        parts.append(f"downloads:[{a.min_downloads} TO null]")
    if a.exclude_trailers:
        parts.append('-title:(trailer) -title:(preview) -subject:(trailer)')
    return " AND ".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection", action="append", help="repeatable, e.g. feature_films Film_Noir SciFi_Horror")
    ap.add_argument("--subject", action="append", help="repeatable, e.g. noir 'science fiction' comedy")
    ap.add_argument("--query", help="raw Lucene fragment, e.g. 'title:(detour)' or 'director:(lang)'")
    ap.add_argument("--year-from", type=int)
    ap.add_argument("--year-to", type=int)
    ap.add_argument("--min-downloads", type=int, default=0)
    ap.add_argument("--rows", type=int, default=25)
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--sort", default="downloads desc", help="e.g. 'downloads desc', 'year asc', 'avg_rating desc'")
    ap.add_argument("--exclude-history", action="store_true", help="drop identifiers already in history.jsonl")
    ap.add_argument("--exclude-trailers", action="store_true", default=True)
    ap.add_argument("--table", action="store_true", help="human-readable instead of JSON")
    a = ap.parse_args()

    q = build_query(a)
    params = {
        "q": q,
        "fl[]": ["identifier", "title", "year", "downloads", "collection", "subject", "description", "avg_rating", "licenseurl", "runtime"],
        "sort[]": a.sort,
        "rows": a.rows,
        "page": a.page,
        "output": "json",
    }
    url = API + "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"error": str(e), "url": url}), file=sys.stderr)
        sys.exit(1)

    skip = history_ids() if a.exclude_history else set()
    out = []
    for d in data.get("response", {}).get("docs", []):
        if d.get("identifier") in skip:
            continue
        desc = d.get("description")
        if isinstance(desc, list):
            desc = " ".join(desc)
        subj = d.get("subject")
        if isinstance(subj, str):
            subj = [subj]
        coll = d.get("collection")
        if isinstance(coll, str):
            coll = [coll]
        # "fav-<user>" pseudo-collections are per-user favourites lists; dozens per item, no signal
        coll = [c for c in (coll or []) if not c.startswith("fav-")]
        out.append({
            "identifier": d.get("identifier"),
            "title": d.get("title"),
            "year": d.get("year"),
            "downloads": d.get("downloads", 0),
            "avg_rating": d.get("avg_rating"),
            "runtime": d.get("runtime"),
            "licenseurl": d.get("licenseurl"),
            "collection": coll,
            "subject": (subj or [])[:8],
            "description": (desc or "")[:240],
        })

    total = data.get("response", {}).get("numFound", 0)
    if a.table:
        print(f"# query: {q}\n# matches: {total}  showing: {len(out)}")
        for d in out:
            print(f"{d['downloads']:>8}  {str(d['year'] or '????'):4}  {d['identifier']:<40}  {d['title']}")
    else:
        print(json.dumps({"query": q, "numFound": total, "results": out}, indent=1))


if __name__ == "__main__":
    main()
