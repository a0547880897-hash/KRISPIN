/**
 * openaiRealtime.js
 * -----------------
 * Opens and configures the WebSocket connection to the OpenAI Realtime API.
 *
 * NOTE (verify at deploy time — these change):
 *  - Model name: OPENAI_REALTIME_MODEL (beta: gpt-4o-realtime-preview, GA: gpt-realtime).
 *  - Event names (input_audio_buffer.speech_started, response.audio.delta, ...)
 *    must match the API version you target. See spec §12.
 */

const WebSocket = require('ws');
const { PERSONA_INSTRUCTIONS } = require('./persona');

const REALTIME_MODEL = process.env.OPENAI_REALTIME_MODEL || 'gpt-4o-realtime-preview';
const AGENT_VOICE = process.env.AGENT_VOICE || 'shimmer';

/**
 * Build the session.update payload. Audio is g711_ulaw in both directions —
 * required to bridge Twilio Media Streams without transcoding.
 */
function buildSessionConfig() {
  return {
    type: 'session.update',
    session: {
      modalities: ['audio', 'text'],
      instructions: PERSONA_INSTRUCTIONS,
      voice: AGENT_VOICE,
      input_audio_format: 'g711_ulaw',
      output_audio_format: 'g711_ulaw',
      input_audio_transcription: { model: 'whisper-1' },
      turn_detection: {
        type: 'server_vad',
        threshold: 0.6,
        prefix_padding_ms: 300,
        silence_duration_ms: 700,
        create_response: true,
        interrupt_response: true,
      },
      temperature: 0.7,
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
      'OpenAI-Beta': 'realtime=v1',
    },
  });

  ws.on('open', () => {
    console.log(`[openai] connected (model=${REALTIME_MODEL}); sending session.update`);
    ws.send(JSON.stringify(buildSessionConfig()));
  });

  ws.on('error', (err) => {
    console.error('[openai] websocket error:', err.message);
  });

  return ws;
}

module.exports = { connectOpenAI, buildSessionConfig, REALTIME_MODEL };
