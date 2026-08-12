/**
 * Frontend Email Service — Bypasses Render SMTP Port Blocking
 *
 * Sends emails directly from the browser over HTTPS (Port 443) using EmailJS or Resend API.
 * Environment Variables (optional in .env or Vercel dashboard):
 *   VITE_EMAILJS_SERVICE_ID
 *   VITE_EMAILJS_TEMPLATE_ID
 *   VITE_EMAILJS_PUBLIC_KEY
 *   VITE_RESEND_API_KEY
 */

/**
 * Send an email directly from the frontend browser over HTTPS (Port 443)
 */
export async function sendEmailFrontend({ to_email, subject, message, link, recipient_name = 'User' }) {
  const emailjsServiceId = import.meta.env.VITE_EMAILJS_SERVICE_ID;
  const emailjsTemplateId = import.meta.env.VITE_EMAILJS_TEMPLATE_ID;
  const emailjsPublicKey = import.meta.env.VITE_EMAILJS_PUBLIC_KEY;
  const resendApiKey = import.meta.env.VITE_RESEND_API_KEY;

  // 1. Try EmailJS via HTTPS REST API (Port 443)
  if (emailjsServiceId && emailjsTemplateId && emailjsPublicKey) {
    try {
      const response = await fetch('https://api.emailjs.com/api/v1.0/email/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          service_id: emailjsServiceId,
          template_id: emailjsTemplateId,
          user_id: emailjsPublicKey,
          template_params: {
            to_email,
            to_name: recipient_name,
            subject,
            message,
            action_link: link || '',
          },
        }),
      });

      if (response.ok) {
        console.log(`[Frontend Email] EmailJS sent email to ${to_email}`);
        return { success: true, provider: 'EmailJS' };
      }
    } catch (err) {
      console.warn('[Frontend Email] EmailJS send failed:', err);
    }
  }

  // 2. Try Resend via HTTPS API (Port 443)
  if (resendApiKey) {
    try {
      const response = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${resendApiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          from: 'AI Tutor <onboarding@resend.dev>',
          to: [to_email],
          subject: subject,
          html: `<p>Hello ${recipient_name},</p><p>${message}</p>${link ? `<p><a href="${link}">Click Here</a></p>` : ''}`,
        }),
      });

      if (response.ok) {
        console.log(`[Frontend Email] Resend sent email to ${to_email}`);
        return { success: true, provider: 'Resend' };
      }
    } catch (err) {
      console.warn('[Frontend Email] Resend API failed:', err);
    }
  }

  console.info(`[Frontend Email] Email simulation to ${to_email}: ${subject} (Link: ${link})`);
  return { success: false, simulated: true, link };
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
