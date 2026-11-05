# Emby

Nearly the same API as Jellyfin (Jellyfin forked from it). Default port 8920 (HTTPS) /
8096 (HTTP) depending on install; Docker image `emby/embyserver` or
`emby/embyserver_arm64v8` for Pi.

`scripts/media_api.py` works unchanged: `ping`, `libraries`, `add-library`, `existing`,
`refresh`. `setup-wizard` may differ on newer Emby versions; if it fails, have the user
finish the wizard in the browser and create an API key under Settings → Advanced → API Keys.

Naming rules are the same as Jellyfin (`Title (Year)/Title (Year).ext`). Emby Premiere is
the paid tier (hardware transcoding, some apps); mention it only if asked.
