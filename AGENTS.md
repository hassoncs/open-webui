## Open WebUI Deployment Notes <!-- oc:id=sec_457fe4 -->

- Public chat surface is `https://chat.ch5.me`.
- Local secure host binding via Caddy is intentionally removed. Do not reintroduce local `:443` for this app unless there is a new explicit requirement.
- The public path is Cloudflare Tunnel first: DNS `chat.ch5.me` points to the named tunnel `open-webui-chat`.
- The tunnel ingress for `open-webui-chat` targets `http://127.0.0.1:24773` on the Mac Mini.

## Mac Mini Runtime <!-- oc:id=sec_906a97 -->

- Host: `macmini.lan`
- Synced service directory: `/Users/radbot/Services/open-webui`
- Container name: `open-webui-devmux`
- Compose file on host: `/Users/radbot/Services/open-webui/docker-compose.yml`
- Container port mapping: `24773:8080`
- Container restart policy: `unless-stopped`

## Tunnel Supervision <!-- oc:id=sec_c5ce5a -->

- LaunchAgent label: `com.radbot.open-webui-cloudflared`
- LaunchAgent file: `/Users/radbot/Library/LaunchAgents/com.radbot.open-webui-cloudflared.plist`
- Runner script: `/Users/radbot/Services/open-webui/run-open-webui-cloudflared.sh`
- Tunnel env file: `/Users/radbot/Services/open-webui/.env`
- Required env var on host: `OPEN_WEBUI_CLOUDFLARE_TUNNEL_TOKEN`

## What Broke Before <!-- oc:id=sec_ba0681 -->

- `chat.ch5.me` was still bound to the Cloudflare tunnel `open-webui-chat`.
- The tunnel existed in Cloudflare but had `0` connections and status `down`.
- Open WebUI itself was healthy on the Mac Mini; the public outage was exposure-layer only.

## Verify <!-- oc:id=sec_c136d2 -->

- Run `scripts/check-macmini-open-webui.sh` from this repo.
- Public proof should show `https://chat.ch5.me` returning `200`.
- Host proof should show tunnel `com.radbot.open-webui-cloudflared` loaded and `open-webui-devmux` healthy.

## Cloudflare Notes <!-- oc:id=sec_5b3252 -->

- Prefer the Cloudflare Tunnel path over local TLS termination.
- If `chat.ch5.me` fails with Cloudflare `1033`, inspect the `open-webui-chat` tunnel before touching the app container.
- Named tunnel config should keep ingress pointed at `http://127.0.0.1:24773`.

## Upstream Policy (Critical — Do Not Violate) <!-- oc:id=sec_9b2650 -->

This repo is a **local fork for fun/ experimenting**. The changes here are not intended to merge upstream.

### Git Remote Layout <!-- oc:id=sec_503b26 -->

- `origin` = `git@github.com:open-webui/open-webui.git` (upstream, read-only in practice)
- `ch5me` = `git@github.com:ch5me/open-webui.git` (private fork, read-write)

### Rules (Always) <!-- oc:id=sec_542003 -->

- **NEVER open a pull request** to `open-webui/open-webui` or `ch5me/open-webui`.
- **NEVER run `gh pr create`**, `hub pr create`, or any PR-creating command.
- **NEVER run `git push origin`**, `gh push origin`, or any command that pushes to `open-webui/open-webui`.
- Do NOT add upstream as a write target.
- Do NOT mention "pull request", "PR", or "upstream merge" unless the user explicitly says **"merge from upstream"**.

### Upstream Sync (Opt-In Only) <!-- oc:id=sec_d67fe1 -->

- The only way upstream changes enter this repo: user says **"merge from upstream"** or equivalent explicit phrase.
- After any upstream merge, verify the app still works locally before continuing.
- Never automatically sync with upstream.

### If Upstream Matters for a Feature <!-- oc:id=sec_79da9e -->

- Cherry-pick or re-implement only the specific commits needed.
- Do not merge upstream `main` as a whole.
- If a feature depends heavily on upstream changes, surface that to the user and stop — do not merge upstream without explicit user approval.

### If You Accidentally Push to Upstream <!-- oc:id=sec_7f7e2e -->

1. Do not attempt to revert or self-correct silently. <!-- oc:id=item_3298b5 -->
1. Report exactly what happened: which remote, which branch, which commits. <!-- oc:id=item_f83108 -->
1. Wait for user instruction. <!-- oc:id=item_757e90 -->
