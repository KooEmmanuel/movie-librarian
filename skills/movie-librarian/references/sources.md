# Free film sources and how to query them

## Contents
1. Internet Archive (primary)
2. Other legal sources
3. Sanity gate
4. What is deliberately excluded

## 1. Internet Archive (primary)

Search API: `scripts/ia_search.py` wraps `https://archive.org/advancedsearch.php`.
Metadata: `https://archive.org/metadata/<identifier>`. Download: `https://archive.org/download/<identifier>/<file>`.
No account or key needed. Be polite: one search at a time, a few seconds between large downloads.

### Collections that return actual feature films

| Collection id | What is in it |
|---|---|
| `feature_films` | the main curated feature-film collection; start here |
| `Film_Noir` | noir, 1940s–50s |
| `SciFi_Horror` | B-movie sci-fi and horror, mostly 1950s–60s |
| `comedy_films` | silent and early sound comedy, Chaplin/Keaton/Lloyd shorts and features |
| `silent_films` | silent era |
| `Classic_cartoons`, `animationandcartoons` | animation (mostly shorts) |
| `westerns` | westerns |
| `more_animation` | more animation |
| `opensource_movies` | user uploads of all kinds, including CC-licensed indie films; noisier |
| `prelinger` | ephemeral/industrial/educational films (great documentaries, few features) |
| `movies` | everything; too broad on its own |

Useful subject terms (`--subject`): `noir`, `"film noir"`, `"science fiction"`, `horror`, `comedy`,
`western`, `drama`, `mystery`, `thriller`, `romance`, `silent`, `documentary`, `animation`,
`"public domain"`, a director's surname, an actor's name. Subjects are free text set by uploaders,
so run the same idea two ways (collection + subject, and a `--query 'title:(...)'`).

Example recipes:

```bash
# Popular noir features
ia_search.py --collection Film_Noir --collection feature_films --subject noir --min-downloads 20000 --rows 30
# 1950s sci-fi
ia_search.py --collection SciFi_Horror --year-from 1950 --year-to 1965 --rows 30
# A specific director
ia_search.py --query 'creator:(Hitchcock) OR director:(Hitchcock)' --collection feature_films
# Creative Commons features from this century
ia_search.py --collection opensource_movies --query 'licenseurl:(*creativecommons*)' --year-from 2000 --min-downloads 5000
```

Fields the search returns per item: `identifier, title, year, downloads, avg_rating, runtime,
licenseurl, collection, subject, description`. `downloads` is the best quality signal: a noir
with 400k downloads is a real, watchable transfer; one with 300 is probably a bad rip or a dupe.

### File choice within an item

`ia_download.py` ranks files: h.264/MPEG4 originals first, then by height, then by size.
It ignores `.ogv` and `512Kb` derivatives unless nothing else exists. Items sometimes have
several encodes of the same film (e.g. a 700 MB mp4 and a 2 GB mkv upload); the larger
better-codec one wins. Use `--file` to override.

## 2. Other legal sources

Secondary. Use them when the user wants something the Archive is thin on (modern open
films, animation, documentaries) or when they ask for a specific title known to be there.

- **Blender Open Movies** (`https://download.blender.org/`, e.g. `/demo/movies/`,
  `/peach/`, `/durian/`, `/mango/`, `/ToS/`, `/Caminandes/`): CC-BY shorts and features
  like *Big Buck Bunny*, *Sintel*, *Tears of Steel*, *Spring*. Direct `curl`, then name as
  `Title (Year)/Title (Year).ext`.
- **Library of Congress National Screening Room** (`https://www.loc.gov/collections/national-screening-room/?fo=json`):
  JSON API; each item has `resources[].files` with mp4 URLs. Mostly shorts and newsreels,
  some features. Public domain or no known restrictions; check the `rights` field.
- **Wikimedia Commons** (`https://commons.wikimedia.org/w/api.php?action=query&list=search&srsearch=...&srnamespace=6&format=json`):
  only CC/PD media; `.webm`/`.ogv`. Good for shorts and a handful of full features.
- **Vimeo / PeerTube with download enabled**: a creator who turned on downloads is giving
  permission. `yt-dlp` works. Do not use `yt-dlp` on a page that has no download button.
- **Studio or distributor free releases**: occasionally a rights holder posts a film for
  free download (not just streaming). Treat case by case; link the source page in history.

## 3. Sanity gate

Why: the Archive is user-uploaded. Among genuine public-domain films sit uploads of
commercial titles that will be taken down. Downloading those puts the user in a bad
spot and makes the whole setup look shady. These checks catch nearly all of them.

Skip an item when any of these is true, and say which rule fired:

1. **Year > 1965 with no Creative Commons / public-domain `licenseurl`.** US copyright for
   anything published 1931 onward can still be in force; between 1931 and 1965 a large
   share of films fell into the public domain through non-renewal, and the curated
   collections above are built from exactly those, so they are reasonably trusted. After
   1965 non-renewal becomes rare, so demand an explicit licence. (As of 2026, everything
   published before 1931 is public domain in the US.)
2. **Title smells like a scene release:** `1080p`, `720p`, `BluRay`, `BRRip`, `WEB-DL`,
   `HDRip`, `x264`, `x265`, `YIFY`, `RARBG`, `DVDRip`, `CAM`, release-group tags in brackets.
3. **Not in a curated collection and under ~2,000 downloads** with no licence field.
4. **Metadata describes it as a trailer, preview, excerpt, or episode**, unless the user
   asked for those.
5. **A well-known still-copyrighted film** by title (any Disney, any Star Wars, any
   post-1980 studio release). You know these; do not pretend otherwise.
6. **Collection is `community` / `opensource_movies` and the uploader's description reads
   like a fan upload** ("enjoy!", "not mine", "for educational purposes").

When the user insists on something the gate rejects, explain the specific rule in one
sentence and offer an alternative. Don't negotiate the rule away.

`autorun.py` applies rules 1–3 mechanically through `taste.rules` in the profile
(`pd_year_max`, `trust_year_max`, `skip_keywords`, `min_downloads`). Rules 4–6 need you.

## 4. What is deliberately excluded

Torrent indexes (including "public domain torrents" sites, because the client and the swarm
mix in non-free content and the user can't audit it), stream-rippers, "123movies"-style
sites, Usenet, Telegram channels, `yt-dlp` against YouTube/Tubi/Pluto/Netflix/Prime even for
free-with-ads content (terms of service forbid downloading). If a user supplies such a URL,
decline that URL in one sentence and continue with the free catalogs.
