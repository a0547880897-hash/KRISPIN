/**
 * server.js
 * ---------
 * Entry point. Express serves Twilio's voice webhook (returns TwiML that connects
 * the call audio to our WebSocket), and a ws server accepts that Media Stream.
 */

require('dotenv').config();

const http = require('http');
const express = require('express');
const { WebSocketServer } = require('ws');
const { handleTwilioConnection } = require('./twilioHandler');

const PORT = process.env.PORT || 3340;
const PUBLIC_HOSTNAME = process.env.PUBLIC_HOSTNAME || '';
// Public path prefix when served behind a reverse proxy on a shared domain,
// e.g. nginx `location /yahav/ -> 127.0.0.1:3340/`. Leave empty if served at root.
// Must start with "/" and have NO trailing slash (e.g. "/yahav").
const PUBLIC_PATH_PREFIX = (process.env.PUBLIC_PATH_PREFIX || '').replace(/\/$/, '');
const STREAM_PATH = '/media-stream';

const app = express();
app.use(express.urlencoded({ extended: false }));
app.use(express.json());

app.get('/health', (_req, res) => res.json({ ok: true }));

/**
 * Twilio voice webhook. Returns TwiML that bridges the call to our Media Stream.
 * The caller's number is passed through as a <Parameter> so we can include it in
 * the summary (Media Stream 'start' events don't carry From otherwise).
 *
 * Twilio configured webhook (per OpenClaw doc): POST /voice/webhook
 */
function twimlHandler(req, res) {
  const from = (req.body && (req.body.From || req.body.from)) || '';
  // Prefer configured public host; fall back to the request's Host header.
  const host = PUBLIC_HOSTNAME || req.headers.host;
  // Include the public path prefix so the proxy routes the WS to this app.
  const streamUrl = `wss://${host}${PUBLIC_PATH_PREFIX}${STREAM_PATH}`;

  const twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="${streamUrl}">
      <Parameter name="from" value="${escapeXml(from)}" />
    </Stream>
  </Connect>
</Response>`;

  res.type('text/xml').send(twiml);
}

app.post('/voice/webhook', twimlHandler);
app.get('/voice/webhook', twimlHandler); // convenience for browser/health checks

function escapeXml(s) {
  return String(s).replace(/[<>&'"]/g, (c) => ({
    '<': '&lt;', '>': '&gt;', '&': '&amp;', "'": '&apos;', '"': '&quot;',
  }[c]));
}

const server = http.createServer(app);

// WebSocket server for the Twilio Media Stream.
const wss = new WebSocketServer({ server, path: STREAM_PATH });
wss.on('connection', (ws) => handleTwilioConnection(ws));

server.listen(PORT, () => {
  console.log(`[server] listening on :${PORT}`);
  console.log(`[server] voice webhook:  POST /voice/webhook  (public: ${PUBLIC_PATH_PREFIX}/voice/webhook)`);
  console.log(`[server] media stream:   wss://${PUBLIC_HOSTNAME || '<host>'}${PUBLIC_PATH_PREFIX}${STREAM_PATH}`);
  if (!PUBLIC_HOSTNAME) {
    console.warn('[server] PUBLIC_HOSTNAME not set — Media Stream URL will use the request Host header. Set it for production.');
  }
});

module.exports = { app, server };
