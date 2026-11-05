#!/usr/bin/env bash
# Detect a media server locally or on a remote host.
# Usage: detect_server.sh [--host HOST] [--json]
# Prints one line per finding; exit 0 even when nothing is found.
set -u
HOST="localhost"; JSON=0
while [ $# -gt 0 ]; do
  case "$1" in
    --host) HOST="$2"; shift 2;;
    --json) JSON=1; shift;;
    *) echo "unknown arg $1" >&2; exit 2;;
  esac
done

found=()
emit() { # kind name detail
  found+=("$1|$2|$3")
  [ $JSON -eq 0 ] && printf '%-10s %-9s %s\n' "$1" "$2" "$3"
}

if [ "$HOST" = "localhost" ]; then
  if command -v docker >/dev/null 2>&1 && docker ps >/dev/null 2>&1; then
    # -a: a stopped media server is still the user's media server (often just didn't come back after a reboot)
    while IFS=$'\t' read -r name image status ports; do
      lc=$(echo "$image $name" | tr '[:upper:]' '[:lower:]')
      kind=""
      case "$lc" in
        *jellyfin*) kind=jellyfin;; *plexinc*|*/plex*|plex*) kind=plex;; *emby*) kind=emby;; *kodi*) kind=kodi;;
      esac
      [ -z "$kind" ] && continue
      mounts=$(docker inspect "$name" --format '{{range .Mounts}}{{.Source}}->{{.Destination}} {{end}}' 2>/dev/null)
      mgr=$(docker inspect "$name" --format '{{if index .Config.Labels "coolify.managed"}}coolify{{else if index .Config.Labels "com.docker.compose.project"}}compose:{{index .Config.Labels "com.docker.compose.project"}}{{else if index .Config.Labels "net.unraid.docker.managed"}}unraid{{else if index .Config.Labels "io.portainer.agent"}}portainer{{end}}' 2>/dev/null)
      ips=$(docker inspect "$name" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' 2>/dev/null)
      emit docker "$kind" "container=$name image=$image status=\"$status\" ports=${ports:-none-published} mounts=[$mounts] managed_by=${mgr:-plain-docker} container_ips=[${ips}]"
    done < <(docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null)
  fi
  for unit in jellyfin plexmediaserver emby-server; do
    if systemctl is-active --quiet "$unit" 2>/dev/null; then
      emit systemd "${unit%%-*}" "unit=$unit active"
    fi
  done
fi

probe() { # addr port name path expect
  local addr="$1"; shift
  local url="http://$addr:$1$3"
  local body
  body=$(curl -s -m 4 -o - -w '\n%{http_code}' "$url" 2>/dev/null) || return 1
  local code=${body##*$'\n'}
  case "$code" in 200|401|301|302) ;; *) return 1;; esac
  emit http "$2" "url=http://$addr:$1 ($4)"
}
if [ "$HOST" = "localhost" ]; then
  ADDRS="127.0.0.1 $(hostname -I 2>/dev/null)"
else
  ADDRS="$HOST"
fi
for addr in $ADDRS; do
  probe "$addr" 8096  jellyfin /System/Info/Public "Jellyfin default port"
  probe "$addr" 8920  emby     /System/Info/Public "Emby default port"
  probe "$addr" 32400 plex     /identity          "Plex default port"
  probe "$addr" 8080  kodi     /jsonrpc           "Kodi web interface default port"
done

if [ $JSON -eq 1 ]; then
  printf '['; sep=""
  for f in "${found[@]:-}"; do
    [ -z "$f" ] && continue
    IFS='|' read -r k n d <<<"$f"
    printf '%s{"kind":"%s","name":"%s","detail":"%s"}' "$sep" "$k" "$n" "$d"; sep=","
  done
  printf ']\n'
elif [ ${#found[@]} -eq 0 ]; then
  echo "nothing found on $HOST (checked docker incl. stopped containers, systemd, ports 8096/8920/32400/8080 on: ${ADDRS})"
fi
