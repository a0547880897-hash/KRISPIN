/**
 * conversation.js
 * ---------------
 * The "conversation culture" (spec §7): barge-in, one-time greeting, bidirectional
 * audio passthrough with zero extra buffering, and transcript collection.
 *
 * These mechanisms live in server code (not the prompt). The VAD tuning is sent
 * in the session config (openaiRealtime.js); here we react to the events it emits.
 *
 * ECHO-RESISTANT BARGE-IN: telephone lines can echo the agent's own voice back
 * into the input, which the VAD reports as `speech_started` — if we interrupt on
 * that instantly, the agent cuts itself off and loops. So we DON'T let the server
 * auto-interrupt (interrupt_response:false in the session) and instead confirm a
 * barge-in ourselves: only interrupt if speech is SUSTAINED past a short window.
 * Echo blips end quickly (speech_stopped before the window) and are ignored;
 * real caller speech persists and triggers the interrupt. Barge-in still works.
 */

// How long caller speech must persist before we treat it as a real interruption
// (ms). Higher = more echo-proof but slightly slower barge-in. Tunable live.
const BARGE_IN_CONFIRM_MS = parseInt(process.env.BARGE_IN_CONFIRM_MS || '350', 10);

const GREETING_INSTRUCTIONS =
  'אמרי בחום, בקצב טבעי ובאינטונציה אנושית (לא מונוטונית), בדיוק: "היי! אני תגל מבנק יהב — מה השם שלך?" משפט אחד בלבד, ואז עצרי והקשיבי. הגי את שמך "תגל" כמו "TAGEL" באנגלית (ההטעמה על GEL) — לא "תאגל". בלי לדקלם, בלי "מצוין".';

/**
 * Create a per-call conversation controller.
 * @param {object} ctx
 * @param {import('ws')} ctx.openaiWs
 * @param {import('ws')} ctx.twilioWs
 */
function createConversation({ openaiWs, twilioWs }) {
  const state = {
    streamSid: null,
    greetingSent: false,
    openaiReady: false,
    agentSpeaking: false, // is the agent currently producing audio?
    bargeInTimer: null, // pending "confirm real interruption" timer
    transcript: [], // [{ role: 'user'|'assistant', text }]
  };

  function setStreamSid(sid) {
    state.streamSid = sid;
    maybeGreet();
  }

  // One-time greeting: fire only once, only after the OpenAI session is ready
  // AND we have a Twilio stream to play it back on. From then on the VAD drives
  // every turn — no further manual response.create. (spec §7.3)
  function maybeGreet() {
    if (state.greetingSent) return;
    if (!state.openaiReady || !state.streamSid) return;
    if (openaiWs.readyState !== openaiWs.OPEN) return;

    openaiWs.send(
      JSON.stringify({
        type: 'response.create',
        response: { instructions: GREETING_INSTRUCTIONS },
      })
    );
    state.greetingSent = true;
    console.log('[conv] greeting sent (once)');
  }

  // Caller audio (Twilio media) -> OpenAI input buffer, immediately. (spec §7.4)
  function forwardCallerAudio(payloadBase64) {
    if (openaiWs.readyState !== openaiWs.OPEN) return;
    openaiWs.send(
      JSON.stringify({ type: 'input_audio_buffer.append', audio: payloadBase64 })
    );
  }

  function cancelBargeInTimer() {
    if (state.bargeInTimer) {
      clearTimeout(state.bargeInTimer);
      state.bargeInTimer = null;
    }
  }

  // Confirmed interruption: stop the agent and flush already-queued audio.
  function performBargeIn() {
    if (openaiWs.readyState === openaiWs.OPEN) {
      openaiWs.send(JSON.stringify({ type: 'response.cancel' }));
    }
    if (state.streamSid && twilioWs.readyState === twilioWs.OPEN) {
      twilioWs.send(JSON.stringify({ event: 'clear', streamSid: state.streamSid }));
    }
    state.agentSpeaking = false;
    console.log('[conv] barge-in confirmed -> agent stopped');
  }

  // Handle every event coming from OpenAI.
  function handleOpenAiEvent(raw) {
    let event;
    try {
      event = JSON.parse(raw);
    } catch {
      return;
    }

    switch (event.type) {
      case 'session.updated':
        state.openaiReady = true;
        maybeGreet();
        break;

      // Agent audio -> Twilio, immediately, no buffering. (spec §7.4)
      // GA: response.output_audio.delta  (beta name kept as fallback)
      case 'response.output_audio.delta':
      case 'response.audio.delta':
        state.agentSpeaking = true;
        if (event.delta && state.streamSid && twilioWs.readyState === twilioWs.OPEN) {
          twilioWs.send(
            JSON.stringify({
              event: 'media',
              streamSid: state.streamSid,
              media: { payload: event.delta },
            })
          );
        }
        break;

      // Agent finished a response naturally.
      case 'response.done':
      case 'response.output_audio.done':
      case 'response.audio.done':
        state.agentSpeaking = false;
        cancelBargeInTimer();
        break;

      // BARGE-IN onset (spec §7.2): caller speech detected. Don't interrupt
      // immediately (could be line echo of the agent). Only arm a confirm timer
      // while the agent is actually speaking; if speech persists past the window
      // it's a real interruption. (interrupt_response is OFF in the session.)
      case 'input_audio_buffer.speech_started':
        if (state.agentSpeaking && !state.bargeInTimer) {
          state.bargeInTimer = setTimeout(() => {
            state.bargeInTimer = null;
            performBargeIn();
          }, BARGE_IN_CONFIRM_MS);
        }
        break;

      // Speech ended before the confirm window -> it was a blip/echo. Ignore.
      case 'input_audio_buffer.speech_stopped':
        cancelBargeInTimer();
        break;

      // Transcript collection (spec §9) — caller side.
      case 'conversation.item.input_audio_transcription.completed':
        if (event.transcript) {
          state.transcript.push({ role: 'user', text: event.transcript.trim() });
        }
        break;

      // Transcript collection — agent side.
      // GA: response.output_audio_transcript.done  (beta name kept as fallback)
      case 'response.output_audio_transcript.done':
      case 'response.audio_transcript.done':
        if (event.transcript) {
          state.transcript.push({ role: 'assistant', text: event.transcript.trim() });
        }
        break;

      case 'error':
        console.error('[openai] event error:', JSON.stringify(event.error || event));
        break;

      default:
        break;
    }
  }

  function getTranscript() {
    return state.transcript;
  }

  return { setStreamSid, forwardCallerAudio, handleOpenAiEvent, getTranscript, state };
}

module.exports = { createConversation, GREETING_INSTRUCTIONS };
