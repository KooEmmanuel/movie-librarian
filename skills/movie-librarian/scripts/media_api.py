#!/usr/bin/env python3
"""Talk to a Jellyfin or Emby server (same API family). Stdlib only.

Config comes from the profile (server.url, server.api_key) or from flags/env:
  --url http://host:8096   --key XXXX   (env: MEDIA_URL, MEDIA_API_KEY)

Subcommands:
  ping                          server name, version, whether the startup wizard is done
  setup-wizard --username U --password P [--movies-path /media/movies]
                                complete a brand-new Jellyfin's first-run wizard (no auth needed)
  create-key --username U --password P [--app movie-librarian]
                                log in as a user and mint an API key, print it
  libraries                     list virtual folders (libraries) with their paths
  add-library --name Movies --path /media/movies
  existing [--since-minutes N] [--json]
                                movies already in the library, 'Title (Year)' one per line
  refresh                       trigger a full library scan
  item-count                    quick sanity count of movies
"""
import argparse, json, os, sys, time, urllib.parse, urllib.request, urllib.error


def home():
    return os.environ.get("MOVIE_LIBRARIAN_HOME") or os.path.expanduser("~/.config/movie-librarian")


def load_profile():
    p = os.path.join(home(), "profile.json")
    if os.path.exists(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


class Api:
    def __init__(self, url, key=None, app="movie-librarian"):
        self.url = url.rstrip("/")
        self.key = key
        self.app = app
        self.token = None  # user access token after login

    def _headers(self, json_body):
        # Jellyfin 10.9+ (and 12.x) want the modern `Authorization: MediaBrowser ...` header;
        # the legacy X-Emby-Authorization alone returns HTTP 400 on login. Emby still reads
        # X-Emby-Token, so send both forms and let the server pick.
        auth = f'MediaBrowser Client="{self.app}", Device="movie-librarian", DeviceId="movie-librarian-1", Version="1.0"'
        tok = self.token or self.key
        if tok:
            auth += f', Token="{tok}"'
        h = {"Accept": "application/json", "Authorization": auth, "X-Emby-Authorization": auth}
        if tok:
            h["X-Emby-Token"] = tok
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    def call(self, method, path, params=None, body=None, raw=False):
        url = self.url + path
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=self._headers(body is not None))
        # A freshly started Jellyfin answers 503 "Server is loading" for up to a minute or two
        # (longer on a Pi while it runs DB migrations). Wait it out instead of failing the setup.
        for attempt in range(40):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    txt = r.read().decode("utf-8", "replace")
                    if raw or not txt:
                        return txt
                    try:
                        return json.loads(txt)
                    except json.JSONDecodeError:
                        return txt
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:300]
                if e.code == 503 and attempt < 39:
                    if attempt == 0:
                        print("server still starting, waiting...", file=sys.stderr)
                    time.sleep(5)
                    continue
                sys.exit(f"HTTP {e.code} on {method} {path}: {detail or e.reason}")
            except urllib.error.URLError as e:
                sys.exit(f"cannot reach {url}: {e.reason}")

    def login(self, username, password):
        r = self.call("POST", "/Users/AuthenticateByName", body={"Username": username, "Pw": password})
        self.token = r["AccessToken"]
        return r


def cmd_ping(api, a):
    info = api.call("GET", "/System/Info/Public")
    print(json.dumps({"ServerName": info.get("ServerName"), "Version": info.get("Version"),
                      "ProductName": info.get("ProductName"), "Id": info.get("Id"),
                      "StartupWizardCompleted": info.get("StartupWizardCompleted"),
                      "OperatingSystem": info.get("OperatingSystem")}, indent=1))


def cmd_setup_wizard(api, a):
    info = api.call("GET", "/System/Info/Public")
    if info.get("StartupWizardCompleted"):
        sys.exit("startup wizard already completed; use create-key instead")
    api.call("POST", "/Startup/Configuration", body={"UICulture": "en-US", "MetadataCountryCode": "US", "PreferredMetadataLanguage": "en"})
    api.call("GET", "/Startup/User")  # Jellyfin requires a GET before the POST is accepted
    api.call("POST", "/Startup/User", body={"Name": a.username, "Password": a.password})
    api.call("POST", "/Startup/RemoteAccess", body={"EnableRemoteAccess": True, "EnableAutomaticPortMapping": False})
    api.call("POST", "/Startup/Complete")
    print("wizard completed; admin user created:", a.username)
    if a.movies_path:
        api.login(a.username, a.password)
        _add_library(api, "Movies", a.movies_path)


def cmd_create_key(api, a):
    api.login(a.username, a.password)
    api.call("POST", "/Auth/Keys", params={"app": a.app})
    keys = api.call("GET", "/Auth/Keys")
    items = keys.get("Items", keys) if isinstance(keys, dict) else keys
    mine = [k for k in items if k.get("AppName") == a.app]
    if not mine:
        sys.exit("key created but not found in listing; check Dashboard → API Keys")
    print(mine[-1]["AccessToken"])


def cmd_libraries(api, a):
    for lib in api.call("GET", "/Library/VirtualFolders"):
        print(f"{lib.get('Name'):<20} type={lib.get('CollectionType') or 'mixed':<8} paths={lib.get('Locations')}")


def _add_library(api, name, path):
    api.call("POST", "/Library/VirtualFolders",
             params={"name": name, "collectionType": "movies", "refreshLibrary": "true"},
             body={"LibraryOptions": {"PathInfos": [{"Path": path}], "EnableRealtimeMonitor": True}})
    print(f"library '{name}' added for {path} and scan started")


def cmd_add_library(api, a):
    _add_library(api, a.name, a.path)


def cmd_existing(api, a):
    params = {"IncludeItemTypes": "Movie", "Recursive": "true", "Fields": "ProductionYear,Path,DateCreated",
              "SortBy": "SortName", "Limit": 5000}
    if a.since_minutes:
        import datetime as dt
        since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=a.since_minutes)
        params["MinDateLastSaved"] = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    r = api.call("GET", "/Items", params=params)
    items = r.get("Items", [])
    if a.json:
        print(json.dumps([{"Name": i.get("Name"), "Year": i.get("ProductionYear"), "Path": i.get("Path")} for i in items], indent=1))
    else:
        for i in items:
            y = i.get("ProductionYear")
            print(f"{i.get('Name')} ({y})" if y else i.get("Name"))
        print(f"# {len(items)} movies", file=sys.stderr)


def cmd_refresh(api, a):
    api.call("POST", "/Library/Refresh")
    print("library scan triggered")


def cmd_item_count(api, a):
    r = api.call("GET", "/Items", params={"IncludeItemTypes": "Movie", "Recursive": "true", "Limit": 0})
    print(r.get("TotalRecordCount"))


def main():
    prof = load_profile()
    srv = prof.get("server", {})
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=os.environ.get("MEDIA_URL") or srv.get("url"))
    ap.add_argument("--key", default=os.environ.get("MEDIA_API_KEY") or srv.get("api_key"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping")
    p = sub.add_parser("setup-wizard"); p.add_argument("--username", required=True); p.add_argument("--password", required=True); p.add_argument("--movies-path")
    p = sub.add_parser("create-key"); p.add_argument("--username", required=True); p.add_argument("--password", required=True); p.add_argument("--app", default="movie-librarian")
    sub.add_parser("libraries")
    p = sub.add_parser("add-library"); p.add_argument("--name", default="Movies"); p.add_argument("--path", required=True)
    p = sub.add_parser("existing"); p.add_argument("--since-minutes", type=int); p.add_argument("--json", action="store_true")
    sub.add_parser("refresh")
    sub.add_parser("item-count")
    a = ap.parse_args()
    if not a.url:
        sys.exit("no server url: pass --url, set MEDIA_URL, or put server.url in the profile")
    api = Api(a.url, a.key)
    globals()["cmd_" + a.cmd.replace("-", "_")](api, a)


if __name__ == "__main__":
    main()
