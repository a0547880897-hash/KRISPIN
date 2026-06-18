/**
 * openaiRealtime.js
 * -----------------
 * Opens and configures the WebSocket connection to the OpenAI Realtime API (GA).
 *
 * GA notes (post-beta, the beta `realtime=v1` interface was removed 2026-05-12):
 *  - No `OpenAI-Beta` header.
 *  - session.update uses `session.type: "realtime"` and nests audio config under
 *    `session.audio.input` / `session.audio.output`.
 *  - For telephony (Twilio g711 u-law / mulaw 8kHz) the audio format is the object
 *    `{ type: "audio/pcmu" }`.
 *  - Model name is configurable; current GA models: gpt-realtime, gpt-realtime-1.5,
 *    gpt-realtime-2, gpt-realtime-mini.
 */

const WebSocket = require('ws');
const { PERSONA_INSTRUCTIONS } = require('./persona');

const REALTIME_MODEL = process.env.OPENAI_REALTIME_MODEL || 'gpt-realtime-2';
const AGENT_VOICE = process.env.AGENT_VOICE || 'shimmer';
// gpt-realtime-2 reasoning intensity: minimal | low | medium | high | xhigh.
// 'high' = smart+flowing for a sales agent; drop to 'medium' if replies feel slow.
const REASONING_EFFORT = process.env.REASONING_EFFORT || 'high';

/**
 * Build the session.update payload (GA shape). Audio is g711 u-law (PCMU) in both
 * directions to bridge Twilio Media Streams without transcoding.
 */
// Reasoning effort is only valid on reasoning realtime models (gpt-realtime-2+).
// Sending it to a non-reasoning model would error, so gate on the model name.
const SUPPORTS_REASONING = /realtime-[2-9]/.test(REALTIME_MODEL);

function buildSessionConfig() {
  return {
    type: 'session.update',
    session: {
      type: 'realtime',
      instructions: PERSONA_INSTRUCTIONS,
      // Session-level reasoning control (no `temperature` for reasoning models).
      ...(SUPPORTS_REASONING && REASONING_EFFORT
        ? { reasoning: { effort: REASONING_EFFORT } }
        : {}),
      audio: {
        input: {
          format: { type: 'audio/pcmu' },
          turn_detection: {
            type: 'server_vad',
            threshold: 0.6,
            prefix_padding_ms: 300,
            silence_duration_ms: 700,
            create_response: true,
            interrupt_response: true,
          },
          transcription: { model: 'whisper-1' },
        },
        output: {
          format: { type: 'audio/pcmu' },
          voice: AGENT_VOICE,
        },
      },
    },
  };
}

/**
 * Open the WebSocket to OpenAI. Sends session.update on open.
 * Returns the (not-yet-open) WebSocket so the caller can attach handlers.
 */
function connectOpenAI() {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY is not set');
  }

  const url = `wss://api.openai.com/v1/realtime?model=${encodeURIComponent(REALTIME_MODEL)}`;
  const ws = new WebSocket(url, {
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
  });

  ws.on('open', () => {
    console.log(`[openai] connected (model=${REALTIME_MODEL}, reasoning=${REASONING_EFFORT}); sending session.update`);
    ws.send(JSON.stringify(buildSessionConfig()));
  });

  ws.on('error', (err) => {
    console.error('[openai] websocket error:', err.message);
  });

  return ws;
}

module.exports = { connectOpenAI, buildSessionConfig, REALTIME_MODEL };
