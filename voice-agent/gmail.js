/**
 * gmail.js
 * --------
 * Sends the end-of-call summary email FROM the configured Gmail account.
 *
 * Sending mail from your Gmail requires an authorized connection (spec/main §). The
 * simplest robust path is a Google **App Password** (needs 2FA enabled on the
 * account): https://myaccount.google.com/apppasswords  -> set GMAIL_APP_PASSWORD.
 *
 * If email is not configured, we log the summary instead of crashing the call.
 */

const nodemailer = require('nodemailer');

let transporter = null;

function getTransporter() {
  if (transporter) return transporter;
  const user = process.env.GMAIL_USER;
  const pass = process.env.GMAIL_APP_PASSWORD;
  if (!user || !pass) return null;

  transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: { user, pass },
  });
  return transporter;
}

/**
 * @param {{ subject: string, body: string }} mail
 * @returns {Promise<boolean>} true if actually sent
 */
async function sendEmail({ subject, body }) {
  const t = getTransporter();
  const to = process.env.SUMMARY_TO || process.env.GMAIL_USER;

  if (!t || !to) {
    console.warn(
      '[gmail] not configured (GMAIL_USER / GMAIL_APP_PASSWORD missing). Summary below:\n' +
        `Subject: ${subject}\n${body}`
    );
    return false;
  }

  await t.sendMail({
    from: process.env.GMAIL_USER,
    to,
    subject,
    text: body,
  });
  console.log(`[gmail] summary email sent to ${to}`);
  return true;
}

module.exports = { sendEmail };
