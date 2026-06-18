/**
 * preflight-openai.js
 * -------------------
 * Verifies the OpenAI Realtime connection BEFORE wiring up Twilio:
 * opens the WebSocket with the real key/model, sends session.update, and waits
 * for `session.updated` (success) or an `error` (bad key/model/config).
 *
 * Run from the app dir (so .env loads):  node deploy/preflight-openai.js
 */

require('dotenv').config();
const { connectOpenAI, REALTIME_MODEL } = require('../openaiRealtime');

console.log(`[preflight] testing OpenAI Realtime with model="${REALTIME_MODEL}"...`);

let finished = false;
const ws = connectOpenAI();

const timer = setTimeout(() => {
  if (finished) return;
  console.error('[preflight] ✗ TIMEOUT: no session.updated within 15s');
  process.exit(1);
}, 15000);

ws.on('message', (data) => {
  let e;
  try { e = JSON.parse(data); } catch { return; }

  if (e.type === 'session.updated') {
    finished = true;
    clearTimeout(timer);
    console.log('[preflight] ✓ OK — session.updated received. Key, model, and GA session config are valid.');
    try { ws.close(); } catch {}
    process.exit(0);
  }
  if (e.type === 'error') {
    finished = true;
    clearTimeout(timer);
    console.error('[preflight] ✗ OpenAI error:', JSON.stringify(e.error || e));
    process.exit(1);
  }
});

ws.on('error', (err) => {
  if (finished) return;
  console.error('[preflight] ✗ WebSocket error:', err.message);
  process.exit(1);
});

ws.on('close', () => {
  if (!finished) {
    console.error('[preflight] ✗ connection closed before session.updated');
    process.exit(1);
  }
});
