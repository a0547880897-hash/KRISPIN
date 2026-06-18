/**
 * twilioHandler.js
 * ----------------
 * Handles one Twilio Media Stream WebSocket connection: bridges it to a fresh
 * OpenAI Realtime connection, and on hang-up triggers the email summary.
 *
 * Twilio Media Streams message events: 'connected', 'start', 'media', 'stop'.
 * Audio payloads are base64-encoded mu-law (g711_ulaw) — same format we set on
 * the OpenAI session, so no transcoding is needed in either direction. (spec §12)
 */

const { connectOpenAI } = require('./openaiRealtime');
const { createConversation } = require('./conversation');
const { sendCallSummary } = require('./summary');

function handleTwilioConnection(twilioWs) {
  console.log('[twilio] media-stream connected');

  const openaiWs = connectOpenAI();
  const conversation = createConversation({ openaiWs, twilioWs });

  const callMeta = {
    callerNumber: null,
    callSid: null,
    startTime: Date.now(),
  };
  let summarySent = false;

  // --- OpenAI -> (conversation controller) ---
  openaiWs.on('message', (data) => conversation.handleOpenAiEvent(data));
  openaiWs.on('close', () => console.log('[openai] connection closed'));

  // --- Twilio -> us ---
  twilioWs.on('message', (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw);
    } catch {
      return;
    }

    switch (msg.event) {
      case 'connected':
        break;

      case 'start': {
        callMeta.startTime = Date.now();
        callMeta.streamSid = msg.start?.streamSid || msg.streamSid;
        callMeta.callSid = msg.start?.callSid || null;
        // Caller number is passed from the TwiML as a <Parameter name="from">.
        const params = msg.start?.customParameters || {};
        callMeta.callerNumber = params.from || params.From || null;
        console.log(
          `[twilio] start streamSid=${callMeta.streamSid} from=${callMeta.callerNumber || 'unknown'}`
        );
        conversation.setStreamSid(callMeta.streamSid);
        break;
      }

      case 'media':
        // Caller audio chunk -> forward to OpenAI immediately.
        if (msg.media?.payload) {
          conversation.forwardCallerAudio(msg.media.payload);
        }
        break;

      case 'stop':
        console.log('[twilio] stop received');
        finish();
        break;

      default:
        break;
    }
  });

  twilioWs.on('close', () => {
    console.log('[twilio] media-stream closed');
    finish();
  });

  twilioWs.on('error', (err) => console.error('[twilio] ws error:', err.message));

  function finish() {
    if (openaiWs.readyState === openaiWs.OPEN || openaiWs.readyState === openaiWs.CONNECTING) {
      try {
        openaiWs.close();
      } catch {
        /* ignore */
      }
    }
    if (summarySent) return;
    summarySent = true;

    sendCallSummary({
      callerNumber: callMeta.callerNumber,
      startTime: callMeta.startTime,
      transcript: conversation.getTranscript(),
    }).catch((err) => console.error('[summary] failed:', err.message));
  }
}

module.exports = { handleTwilioConnection };
