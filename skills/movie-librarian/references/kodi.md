# Kodi (and "just a folder")

Kodi is a player, not a server: it scans a folder it can reach (local, SMB, NFS). Set
`server.type` to `kodi` and `library.movies_path` to the folder Kodi's source points at.
Naming is the same `Title (Year)/Title (Year).ext` convention.

Refresh: Kodi scans on startup if "Update library on startup" is enabled. To trigger
remotely, enable Settings → Services → Control → "Allow remote control via HTTP"
(default port 8080, set a username/password) then:

```bash
curl -s -u USER:PASS -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"VideoLibrary.Scan","id":1}' http://HOST:8080/jsonrpc
```

Put `http://HOST:8080` in `server.url` and `USER:PASS` in `server.api_key` for that.

`"type": "folder"` means no refresh step at all: the user has some other player (VLC,
Infuse, a smart TV reading SMB). Still name files properly so a future server picks them
up cleanly.
