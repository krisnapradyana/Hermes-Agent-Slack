# Google Drive Mount — Recovery Guide

**For:** the `/gdrive` rclone mount on the SuperPixel server (feeds Hermes, assistant-web, and the web UI's folder picker).
**Folder naming:** the server's stack directory is `~/Hermes-Agent-Slack` — it's the same folder mirrored on the PC as `C:\Hermes-Local`.
**When to use:** Hermes says the drive is inaccessible ("Transport endpoint is not connected"), the folder picker shows "Could not read folder", or `ls /gdrive` hangs or errors.
**Written after:** the Sep 2026 outage (full disk → zombie mount → token re-auth → wrong team_drive). Every fix below was battle-tested then.

---

## The 60-second fix (try this first)

One command, installed at `~/gdrive-fix.sh` on the server:

```bash
~/gdrive-fix.sh
```

It remounts the drive, bounces the containers, and verifies from inside assistant-web.
Prints `ALL GOOD` → done. Prints `MOUNT STILL DEAD` → go to the Decision Tree below.

If the script is missing, recreate it:

```bash
cat > ~/gdrive-fix.sh <<'EOF'
#!/bin/bash
set -x
sudo systemctl stop gdrive.service
sudo umount -l /gdrive 2>/dev/null
sudo systemctl start gdrive.service
sleep 10
timeout 30 ls /gdrive | head || { echo "MOUNT STILL DEAD - check token/team_drive"; exit 1; }
cd ~/Hermes-Agent-Slack && sudo docker compose restart assistant-web hermes
sleep 5
sudo docker exec assistant-web ls /gdrive | head && echo "ALL GOOD"
EOF
chmod +x ~/gdrive-fix.sh
```

---

## How this system fits together (know your enemy)

- `gdrive.service` (systemd) runs **rclone** as user `krisnapradyana`, FUSE-mounting Google Drive at `/gdrive`.
- The Google account's **My Drive** is the content root (`team_drive` in the rclone config must be **empty** — the "Hermes-Agent-Access" Shared Drive is NOT where the files live).
- Containers see `/gdrive` via `rshared` bind mounts — but if the mount dies while they run, they keep the corpse until **restarted**.
- rclone stages all reads/writes in a local cache (capped 5G). **A full disk kills the mount** — that was the root cause of the Sep 2026 outage.
- A cron watchdog (`/etc/cron.d/gdrive-health`) checks the mount every 5 min and restarts the service if `/gdrive` doesn't answer within 60s.

---

## Decision tree

### Step 1 — Is the disk full?

```bash
df -h /
```

**≥ 90% used → clean it first.** A full disk is the #1 killer of this mount:

```bash
~/docker-clean.sh
```

(or manually: `sudo docker builder prune -af && sudo docker image prune -af && sudo docker container prune -f && sudo docker volume prune -f`)

### Step 2 — Remount on the host

```bash
sudo systemctl stop gdrive.service
sudo umount -l /gdrive 2>/dev/null
sudo systemctl start gdrive.service
sleep 10
timeout 30 ls /gdrive | head
```

- **Familiar files listed** (`2024 PROJECTS/`, `(SHARED) UNITHREE TIMELINE.xlsx`, …) → go to Step 3.
- **Hangs / "Terminated"** → go to Step 4 (token check).
- **Lists but WRONG or EMPTY content** → go to Step 5 (team_drive check).

### Step 3 — Bounce the containers

Running containers keep a dead mount. `docker compose up -d` does NOT restart them — use `restart`:

```bash
cd ~/Hermes-Agent-Slack && sudo docker compose restart assistant-web hermes
sudo docker exec assistant-web ls /gdrive | head
```

- **Files listed** → DONE. Reload the web UI; tell Hermes to retry.
- **Container still can't see it while the host can** → force recreate:

```bash
cd ~/Hermes-Agent-Slack && sudo docker compose up -d --force-recreate assistant-web hermes
```

### Step 4 — Token check (mount hangs or auth errors in logs)

Test Google connectivity directly, skipping the mount machinery:

```bash
rclone lsf --drive-team-drive "" gdrive: | head -10
```

- **Files listed** → token is fine; the problem is FUSE/mount — check logs:
  `sudo journalctl -u gdrive.service -n 30 --no-pager`
- **`invalid_grant` / `token expired` / auth error** → Google revoked the login. Full re-auth:

  **On the server:**
  ```bash
  rclone config reconnect gdrive:
  ```
  Answer: **y** (refresh token) → **n** (auto config — this is a headless server!).
  It prints an `rclone authorize "drive" "..."` command.

  **On your Windows PC** (install once with `winget install Rclone.Rclone`):
  run that exact `rclone authorize` command → browser opens → sign in with the
  **account that owns the SuperPixel files** (the one whose My Drive has
  `2024 PROJECTS`) → copy the `{...}` token JSON it prints.

  **Back on the server:** paste the token at the `config_token>` prompt.
  When asked **"Configure this as a Shared Drive (Team Drive)?" answer n** —
  the files are in My Drive. (Answering y here caused the Sep 2026 wrong-drive bug.)

  Then repeat from Step 2.

### Step 5 — Wrong/empty content (mount works but files are missing)

The remote is pointing at the wrong place. Check:

```bash
grep -E 'team_drive|root_folder_id' ~/.config/rclone/rclone.conf
```

Correct state: **both empty** (`team_drive =` with nothing after it). If `team_drive` has an ID:

```bash
sed -i 's/^team_drive = .*/team_drive =/' ~/.config/rclone/rclone.conf
```

Then repeat from Step 2.

If config is clean but content is still wrong → the token belongs to the wrong
Google account (e.g. one that sees RK/Petco drives instead of SuperPixel files).
Redo Step 4's re-auth in an **incognito browser window** and pick the right account.

---

## After recovery — checklist

```bash
timeout 30 ls /gdrive | head                      # host sees files
sudo docker exec assistant-web ls /gdrive | head  # container sees files
df -h /                                           # disk has headroom
cat /etc/cron.d/gdrive-health                     # watchdog is installed
```

Watchdog missing? Reinstall it:

```bash
echo '*/5 * * * * root timeout 60 ls /gdrive >/dev/null 2>&1 || /usr/bin/systemctl restart gdrive.service' | sudo tee /etc/cron.d/gdrive-health
```

Also worth doing after any outage: ask Hermes to regenerate `SUPERPIXEL/TEAM-STATUS.md`
and `PROJECT-TRACKER.md` once — writes that failed during the outage may be lost.

---

## Known traps (learned the hard way)

1. **The login banner lies.** The "Usage of /" in the SSH welcome message is from your *previous* login. Always run `df -h /` for the live number.
2. **`systemctl` sees a healthy process on a dead mount.** A broken FUSE mount usually leaves rclone running, so `Restart=on-failure` never fires and `is-active` says `active`. Trust `ls /gdrive`, not the service status. (This is why the watchdog exists.)
3. **`docker compose up -d` won't fix a container's stale mount.** It only recreates containers whose config changed. Use `restart` or `--force-recreate`.
4. **Never run `rclone mount` with `sudo`.** Root has no rclone config — it fails with "didn't find section in config file". The service runs it as the right user.
5. **The Shared Drive question is a trap.** During reconnect, answering **y** points the remote at the empty "Hermes-Agent-Access" Shared Drive and everything looks deleted. It isn't — answer **n**, files live in My Drive.
6. **First `ls` after a fresh mount can be slow.** The dir cache rebuilds; give it up to a minute before declaring it dead. (The watchdog's 60s timeout accounts for this — don't shorten it.)
