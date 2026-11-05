# The media server is on another machine

## Contents
1. Find out what you're dealing with
2. Get SSH working
3. Where downloads should run
4. NAS and appliance quirks

## 1. Find out what you're dealing with

Ask for: hostname or IP, what it is (NAS brand, a PC, a Pi, a VPS), the SSH username
if they know it, and whether they've SSH'd into it before from this machine. Then:

```bash
scripts/detect_server.sh --host <ip>          # which media ports answer
ssh -o BatchMode=yes -o ConnectTimeout=5 <user>@<ip> 'echo ok; uname -a; id'
```

`ok` means key auth already works; go to section 3. "Permission denied (publickey,password)"
means SSH is up but no key is trusted yet. Timeout means SSH is off, firewalled, or the IP
is wrong; ask them to enable SSH on the device (NAS: Control Panel → Terminal & SNMP on
Synology, Settings → SSH on QNAP/Unraid/TrueNAS) and confirm the IP from its UI.

## 2. Get SSH working

Explain the idea in one line: "I'll create a key on this machine and add its public half
to the server, so scripts can log in without a password." Then:

1. Reuse an existing key if one exists (`ls ~/.ssh/id_ed25519.pub ~/.ssh/id_rsa.pub`).
   Otherwise, after they agree: `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N "" -C "movie-librarian@$(hostname)"`.
2. Install the public key. The clean way needs their password once, interactively, so
   they run it themselves (tell them to type `! ssh-copy-id -i ~/.ssh/id_ed25519.pub user@ip`
   in this session). If `ssh-copy-id` is missing, show them the equivalent:
   `cat ~/.ssh/id_ed25519.pub | ssh user@ip 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys'`.
   If they would rather paste the key into the NAS web UI (Synology and TrueNAS have a
   field for it), print the public key for them.
3. Add a host alias so every later command is short and the profile stores just a name:

   ```
   # ~/.ssh/config
   Host nas
     HostName 192.168.1.20
     User admin
     IdentityFile ~/.ssh/id_ed25519
     IdentitiesOnly yes
   ```

4. Verify with `ssh -o BatchMode=yes nas 'echo ok'`. Store `nas` as `server.ssh_host` and
   set `library.remote: true`.

If they offer to paste a *private* key into the chat, steer them away: it belongs in
`~/.ssh/` with mode 600, and they should copy it there themselves. Never log or echo it.

## 3. Where downloads should run

Default: run `curl` on the remote server (`ia_download.py --remote nas`). The file goes
straight from the Archive to the disk it will live on; this machine only orchestrates.
Needs `curl` and `md5sum` on the remote (every NAS has them; `ssh nas 'command -v curl md5sum'`).

Fallback when the remote has no outbound internet or no curl: download locally to a
staging folder, then `rsync -a --partial --progress <staging>/ nas:<movies_path>/`, then
delete the local copy. Say which one you are doing and why.

Check free space on the remote before a run: `ssh nas 'df -h <movies_path>'`.

Ownership: files created over SSH belong to the SSH user. The media server process must
be able to read them. On a Synology that's usually fine (shared folder ACLs). In Docker
on a generic host, `chown` to the container's UID or run the download as that user.

## 4. NAS and appliance quirks

- **Synology:** SSH user must be in `administrators`. Docker is "Container Manager".
  Paths look like `/volume1/video/movies`. Jellyfin package also exists in SynoCommunity.
- **Unraid:** `/mnt/user/media/movies`. Docker templates via Community Apps; the compose
  file still applies if they prefer.
- **TrueNAS SCALE:** apps run in Kubernetes/Docker depending on version; the host path
  is a dataset like `/mnt/tank/media/movies`. SSH as root is often disabled; use an admin
  user with sudo.
- **A VPS / cloud box:** fine, but remind them that the Archive download counts against
  the VPS's bandwidth and that streaming home from a VPS depends on its upload speed.
- **Windows PC running Plex/Jellyfin:** SSH exists (OpenSSH Server feature) but paths are
  `C:\Media\Movies`; `curl` is present on Windows 10+; `md5sum` is not (use
  `certutil -hashfile`). Simplest is often to download locally and copy over SMB.
