/**
 * conversation.js
 * ---------------
 * The "conversation culture" (spec §7): barge-in, one-time greeting, bidirectional
 * audio passthrough with zero extra buffering, and transcript collection.
 *
 * These mechanisms live in server code (not the prompt). The VAD tuning is sent
 * in the session config (openaiRealtime.js); here we react to the events it emits.
 */

const GREETING_INSTRUCTIONS =
  'אמרי בחום, בקצב טבעי ובאינטונציה אנושית (לא מונוטונית), בדיוק: "היי! אני תגל מבנק יהב — מה השם שלך?" משפט אחד בלבד, ואז עצרי והקשיבי. שימי לב להגיית שמך: "תגל" נהגה טַגֵל (Ta-GEL), שתי הברות, בלי תנועת A באמצע — לא "תָאגֵל". בלי לדקלם, בלי "מצוין".';

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

      // BARGE-IN: caller started talking while agent was talking. (spec §7.2)
      // 1) cancel the agent's in-flight response on OpenAI
      // 2) clear audio already queued to Twilio but not yet played
      case 'input_audio_buffer.speech_started':
        if (openaiWs.readyState === openaiWs.OPEN) {
          openaiWs.send(JSON.stringify({ type: 'response.cancel' }));
        }
        if (state.streamSid && twilioWs.readyState === twilioWs.OPEN) {
          twilioWs.send(
            JSON.stringify({ event: 'clear', streamSid: state.streamSid })
          );
        }
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
