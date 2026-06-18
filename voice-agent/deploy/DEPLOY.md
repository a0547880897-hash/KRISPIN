# Deployment — Yahav voice sales agent (alongside the existing voice-server)

Target server: DigitalOcean droplet `167.172.182.173`, Ubuntu 24.04, Node v24, nginx 1.24.

This deploys the new **Bank Yahav sales agent** WITHOUT touching the existing
`voice-server.service` (port 8080) or OpenClaw (port 18789). Layout:

| What | Value |
|------|-------|
| App dir | `/opt/yahav/voice-agent` |
| Internal port | `3340` (currently free) |
| Public domain | `167-172-182-173.sslip.io` (existing valid SSL) |
| Public path | `/yahav/` (new nginx location → 127.0.0.1:3340) |
| Twilio webhook | `https://167-172-182-173.sslip.io/yahav/voice/webhook` |
| systemd service | `yahav-voice-agent.service` |

## Steps

1. **Get the code** (private repo → use a fine-grained read-only PAT; if public, drop the token):
   ```bash
   git clone https://<GITHUB_TOKEN>@github.com/a0547880897-hash/KRISPIN.git /opt/yahav
   cd /opt/yahav && git checkout claude/kind-heisenberg-guxz1l
   cd /opt/yahav/voice-agent && npm install --omit=dev
   ```

2. **Create `.env`** (`/opt/yahav/voice-agent/.env`). Secrets are filled by the
   operator, never shared in chat:
   ```
   OPENAI_API_KEY=<new OpenAI key>
   OPENAI_REALTIME_MODEL=gpt-realtime-2
   REASONING_EFFORT=high
   OPENAI_SUMMARY_MODEL=gpt-4o-mini
   AGENT_VOICE=shimmer
   PORT=3340
   PUBLIC_HOSTNAME=167-172-182-173.sslip.io
   PUBLIC_PATH_PREFIX=/yahav
   TWILIO_AUTH_TOKEN=<new Twilio token, optional>
   BUSINESS_NAME=בנק יהב
   GMAIL_USER=<your gmail>
   GMAIL_APP_PASSWORD=<gmail app password>
   SUMMARY_TO=<your gmail>
   ```

3. **systemd service**:
   ```bash
   cp /opt/yahav/voice-agent/deploy/yahav-voice-agent.service /etc/systemd/system/
   systemctl daemon-reload
   systemctl enable --now yahav-voice-agent
   systemctl status yahav-voice-agent --no-pager
   curl -s http://127.0.0.1:3340/health     # expect {"ok":true}
   ```

4. **nginx** — add the location to the EXISTING 443 server block (do not create a
   second server block for the same name). Insert the contents of
   `deploy/nginx-yahav.location` inside `server { listen 443 ssl; server_name 167-172-182-173.sslip.io; ... }`, then:
   ```bash
   nginx -t && systemctl reload nginx
   curl -s https://167-172-182-173.sslip.io/yahav/health   # expect {"ok":true}
   ```

5. **Twilio** — point the NEW number (+972 53 563 5573) Voice webhook to:
   `https://167-172-182-173.sslip.io/yahav/voice/webhook` (HTTP POST).

6. **SSL renewal** — the cert expires soon; confirm auto-renew:
   ```bash
   systemctl status certbot.timer --no-pager ; certbot renew --dry-run
   ```

## Updating later
```bash
cd /opt/yahav && git pull && cd voice-agent && npm install --omit=dev
systemctl restart yahav-voice-agent
```
