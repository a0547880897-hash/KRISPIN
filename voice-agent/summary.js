/**
 * summary.js
 * ----------
 * At hang-up: turn the transcript into a structured sales summary (via the
 * OpenAI chat endpoint) and email it (gmail.js). Email — not WhatsApp — per the
 * sales-agent spec.
 */

const { sendEmail } = require('./gmail');

const SUMMARY_MODEL = process.env.OPENAI_SUMMARY_MODEL || 'gpt-4o-mini';

function transcriptToText(transcript) {
  if (!Array.isArray(transcript) || transcript.length === 0) return '';
  return transcript
    .map((t) => `${t.role === 'assistant' ? 'סוכן' : 'לקוח'}: ${t.text}`)
    .join('\n');
}

/**
 * Ask GPT to produce the four structured sections from the transcript.
 * Falls back to the raw transcript if the API is unavailable.
 */
async function summarizeTranscript(transcript) {
  const text = transcriptToText(transcript);
  if (!text) return null;

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) return { raw: text };

  const prompt = `להלן תמליל שיחת מכירה בין סוכן בנק יהב ללקוח. הפק סיכום בעברית, ענייני וקצר, במבנה הבא בדיוק:

אפיון הלקוח: (מצב נוכחי, צרכים, מה חשוב לו)
מה הוצע: (איזה חשבון הוצע, והאם הוצעה הלוואה)
התעניינות: (חשבון בלבד / גם הלוואה / כלום)
סיכום השיחה: (תמצית קצרה של מהלך השיחה)

תמליל:
${text}`;

  try {
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: SUMMARY_MODEL,
        messages: [{ role: 'user', content: prompt }],
        temperature: 0.3,
      }),
    });
    if (!res.ok) {
      console.error('[summary] chat API error:', res.status, await res.text());
      return { raw: text };
    }
    const data = await res.json();
    const content = data?.choices?.[0]?.message?.content?.trim();
    return content ? { structured: content } : { raw: text };
  } catch (err) {
    console.error('[summary] summarize failed:', err.message);
    return { raw: text };
  }
}

function buildEmailBody({ callerNumber, startTime, summary }) {
  const now = new Date(startTime || Date.now());
  const date = now.toLocaleDateString('he-IL');
  const time = now.toLocaleTimeString('he-IL');

  const body =
    summary?.structured ||
    (summary?.raw ? `תמליל גולמי:\n${summary.raw}` : 'לא נאסף תמליל לשיחה זו.');

  return `📞 מספר המחייג: ${callerNumber || 'לא ידוע'}
🕐 שעה: ${time} | 📅 תאריך: ${date}

${body}`;
}

/**
 * Main entry point called by twilioHandler on hang-up.
 */
async function sendCallSummary({ callerNumber, startTime, transcript }) {
  const summary = await summarizeTranscript(transcript);
  const now = new Date(startTime || Date.now());
  const date = now.toLocaleDateString('he-IL');

  const subject = `סיכום שיחת מכירה — בנק יהב — ${date}`;
  const body = buildEmailBody({ callerNumber, startTime, summary });

  await sendEmail({ subject, body });
}

module.exports = { sendCallSummary, summarizeTranscript, buildEmailBody, transcriptToText };
