/**
 * Frontend Email Service — SMTP-only, sent from the browser
 *
 * Browsers can't speak SMTP, so the SMTP account (Gmail etc.) is
 * connected inside EmailJS (emailjs.com) and this module calls its HTTPS API
 * over Port 443. This is the ONLY email service in the app — your SMTP
 * credentials stay server-side on EmailJS, never in this bundle.
 *
 * Environment Variables (set in Vercel dashboard):
 *   VITE_EMAILJS_SERVICE_ID
 *   VITE_EMAILJS_TEMPLATE_ID
 *   VITE_EMAILJS_PUBLIC_KEY
 */

export const emailServiceConfigured = () =>
  Boolean(
    import.meta.env.VITE_EMAILJS_SERVICE_ID &&
    import.meta.env.VITE_EMAILJS_TEMPLATE_ID &&
    import.meta.env.VITE_EMAILJS_PUBLIC_KEY
  );

/**
 * Send an email from the browser via EmailJS (SMTP sandboxed on EmailJS' side).
 */
export async function sendEmailFrontend({ to_email, subject, message, link, recipient_name = 'User', action_text = 'Open Link' }) {
  const serviceId = import.meta.env.VITE_EMAILJS_SERVICE_ID;
  const templateId = import.meta.env.VITE_EMAILJS_TEMPLATE_ID;
  const publicKey = import.meta.env.VITE_EMAILJS_PUBLIC_KEY;

  if (!serviceId || !templateId || !publicKey) {
    console.info(`[Frontend Email] EmailJS not configured — email to ${to_email} skipped (${subject})`);
    return { success: false, simulated: true, link };
  }

  try {
    const response = await fetch('https://api.emailjs.com/api/v1.0/email/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service_id: serviceId,
        template_id: templateId,
        user_id: publicKey,
        template_params: {
          to_email,
          to_name: recipient_name,
          subject,
          message,
          action_link: link || '',
          action_text,
          year: new Date().getFullYear(),
        },
      }),
    });

    if (response.ok) {
      console.log(`[Frontend Email] EmailJS sent email to ${to_email}`);
      return { success: true, provider: 'EmailJS' };
    }
    const errText = await response.text().catch(() => '');
    console.warn(`[Frontend Email] EmailJS send failed (${response.status}): ${errText}`);
  } catch (err) {
    console.warn('[Frontend Email] EmailJS send failed:', err);
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
    action_text: 'Verify Email',
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
    action_text: 'Reset Password',
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
    action_text: 'Open AI Tutor',
  });
}