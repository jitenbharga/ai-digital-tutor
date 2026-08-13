/**
 * Frontend Email Service — SMTP sent from the browser via smtp.js (smtpjs.com)
 *
 * Browsers can't open raw SMTP sockets, so smtp.js (loaded from the CDN in
 * index.html) relays the message through its SMTP gateway using the account
 * configured below. NOTE: the SMTP credentials are embedded in the client
 * bundle (VITE_* vars reach the browser) — anyone can extract them, so use a
 * dedicated sending account (Gmail with an App Password) and never your
 * personal credentials.
 *
 * Environment Variables (set in Vercel dashboard):
 *   VITE_SMTP_HOST       e.g. smtp.gmail.com
 *   VITE_SMTP_USER       the sending account
 *   VITE_SMTP_PASSWORD   Gmail App Password (Google > Security > 2-Step Verification > App passwords)
 *   VITE_SMTP_FROM       e.g. AI Tutor <youraddress@gmail.com>
 */

export const emailServiceConfigured = () =>
  Boolean(
    import.meta.env.VITE_SMTP_HOST &&
    import.meta.env.VITE_SMTP_USER &&
    import.meta.env.VITE_SMTP_PASSWORD &&
    import.meta.env.VITE_SMTP_FROM
  );

/**
 * Send an email from the browser via SMTP (smtp.js CDN library).
 */
export async function sendEmailFrontend({ to_email, subject, message, link, recipient_name = 'User' }) {
  if (!emailServiceConfigured()) {
    console.info(`[Frontend Email] SMTP not configured — email to ${to_email} (${recipient_name}) skipped (${subject})`);
    return { success: false, simulated: true, link };
  }

  if (typeof window.Email?.send !== 'function') {
    console.warn('[Frontend Email] smtp.js is not loaded (CDN blocked?) — email skipped');
    return { success: false, simulated: false, link };
  }

  try {
    const result = await window.Email.send({
      Host: import.meta.env.VITE_SMTP_HOST,
      Username: import.meta.env.VITE_SMTP_USER,
      Password: import.meta.env.VITE_SMTP_PASSWORD,
      To: to_email,
      From: import.meta.env.VITE_SMTP_FROM,
      Subject: subject,
      Body: link ? `${message}\n\n${link}` : message,
    });

    if (result === 'OK') {
      console.log(`[Frontend Email] SMTP sent email to ${to_email}`);
      return { success: true, provider: 'SMTP' };
    }
    console.warn(`[Frontend Email] SMTP returned unexpected response:`, result);
  } catch (err) {
    console.warn('[Frontend Email] SMTP send failed:', err);
  }

  return { success: false, simulated: false, link };
}

/**
 * Send Account Verification Email from Frontend
 */
export async function sendVerificationEmail(to_email, username, verify_link) {
  return sendEmailFrontend({
    to_email,
    recipient_name: username,
    subject: 'Verify your AI Tutor Account',
    message: `Thank you for signing up! Please verify your email to activate your AI Tutor account.`,
    link: verify_link,
  });
}

/**
 * Send Password Reset Email from Frontend
 */
export async function sendPasswordResetEmail(to_email, username, reset_link) {
  return sendEmailFrontend({
    to_email,
    recipient_name: username,
    subject: 'Reset your AI Tutor Password',
    message: `You requested a password reset. Click the link below to set a new password.`,
    link: reset_link,
  });
}

/**
 * Send Guardian Invite Email from Frontend
 */
export async function sendGuardianInviteEmail(to_email, student_name, invite_code) {
  return sendEmailFrontend({
    to_email,
    recipient_name: 'Guardian',
    subject: `Parent/Guardian Invite from ${student_name}`,
    message: `${student_name} has invited you to view their learning progress on AI Tutor. Your invite code is: ${invite_code}`,
    link: '',
  });
}