"""
Ultra-Premium HTML & Plaintext Email Templates for AI Digital Tutor.
Designed with modern typography, gradient headers, responsive cards, and crisp CTAs.
"""


def _base_email_wrapper(title: str, subtitle: str, content_html: str) -> str:
    """Wrap content in a stunning, responsive, dark/light theme-friendly email container."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 40px 16px;">
        <tr>
            <td align="center">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width: 580px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04);">
                    <!-- Header with Gradient -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); padding: 40px 32px; text-align: center;">
                            <div style="display: inline-block; background: rgba(255, 255, 255, 0.15); border-radius: 12px; padding: 10px 16px; margin-bottom: 16px; backdrop-filter: blur(8px);">
                                <span style="color: #ffffff; font-weight: 800; font-size: 18px; letter-spacing: 1px;">🎓 AI DIGITAL TUTOR</span>
                            </div>
                            <h1 style="color: #ffffff; font-size: 24px; font-weight: 700; margin: 0; line-height: 1.3;">{title}</h1>
                            <p style="color: #e0e7ff; font-size: 15px; margin: 8px 0 0 0; opacity: 0.9;">{subtitle}</p>
                        </td>
                    </tr>
                    <!-- Body Content -->
                    <tr>
                        <td style="padding: 36px 32px; color: #334155; font-size: 16px; line-height: 1.6;">
                            {content_html}
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8fafc; padding: 24px 32px; border-top: 1px solid #e2e8f0; text-align: center; color: #94a3b8; font-size: 13px; line-height: 1.5;">
                            <p style="margin: 0 0 6px 0; font-weight: 600; color: #64748b;">AI Digital Tutor Inc. &bull; Personalized Learning Engine</p>
                            <p style="margin: 0;">This email was sent to you because an action was requested on your account.<br>If you have questions, contact <a href="mailto:support@aidigitaltutor.com" style="color: #4f46e5; text-decoration: none;">support@aidigitaltutor.com</a></p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def verification_email(link: str) -> tuple[str, str, str]:
    """Return (subject, html, text) for email verification."""
    subject = "Verify your email — AI Digital Tutor"
    title = "Confirm Your Email Address"
    subtitle = "Just one more step to unlock your AI learning workspace"

    content_html = f"""
    <p style="margin-top: 0; font-size: 16px; color: #1e293b; font-weight: 600;">Welcome to AI Digital Tutor! 👋</p>
    <p style="color: #475569; margin-bottom: 28px;">Thank you for signing up. Please verify your email address to activate your account and start your AI-powered personalized learning journey.</p>
    
    <div style="text-align: center; margin: 32px 0;">
        <a href="{link}" style="background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%); color: #ffffff; text-decoration: none; padding: 16px 36px; border-radius: 12px; font-weight: 700; font-size: 16px; display: inline-block; box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35);">Verify Email Address &rarr;</a>
    </div>
    
    <div style="background-color: #f1f5f9; border-left: 4px solid #4f46e5; padding: 16px; border-radius: 0 8px 8px 0; margin-top: 28px;">
        <p style="margin: 0; font-size: 13px; color: #64748b; line-height: 1.5;">
            <strong>Link expired or not working?</strong> Copy and paste this URL into your browser:<br>
            <span style="word-break: break-all; color: #4f46e5;">{link}</span>
        </p>
    </div>
    
    <p style="color: #94a3b8; font-size: 13px; margin-top: 24px; margin-bottom: 0;">⏱️ This verification link expires in <strong>24 hours</strong> for security reasons.</p>
    """

    text = f"Welcome to AI Digital Tutor!\n\nPlease verify your email by opening this link: {link}\n\nLink expires in 24 hours."
    html = _base_email_wrapper(title, subtitle, content_html)
    return subject, html, text


def password_reset_email(link: str) -> tuple[str, str, str]:
    """Return (subject, html, text) for password reset."""
    subject = "Reset your password — AI Digital Tutor"
    title = "Password Reset Request"
    subtitle = "We received a request to reset your password"

    content_html = f"""
    <p style="margin-top: 0; font-size: 16px; color: #1e293b; font-weight: 600;">Need to reset your password? 🔑</p>
    <p style="color: #475569; margin-bottom: 28px;">Click the button below to choose a new password for your account. If you didn't ask for a reset, you can safely ignore this email.</p>
    
    <div style="text-align: center; margin: 32px 0;">
        <a href="{link}" style="background: linear-gradient(135deg, #4f46e5 0%, #6366f1 100%); color: #ffffff; text-decoration: none; padding: 16px 36px; border-radius: 12px; font-weight: 700; font-size: 16px; display: inline-block; box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35);">Reset Password &rarr;</a>
    </div>
    
    <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 16px; border-radius: 0 8px 8px 0; margin-top: 28px;">
        <p style="margin: 0; font-size: 13px; color: #991b1b; line-height: 1.5;">
            <strong>Security Alert:</strong> This link is single-use and expires in <strong>1 hour</strong>. If you did not make this request, please review your account security.
        </p>
    </div>
    
    <p style="color: #64748b; font-size: 13px; margin-top: 20px; word-break: break-all;">
        Or copy and paste this link: <span style="color: #4f46e5;">{link}</span>
    </p>
    """

    text = f"Reset your password on AI Digital Tutor:\n\nOpen this link: {link}\n\nLink expires in 1 hour."
    html = _base_email_wrapper(title, subtitle, content_html)
    return subject, html, text


def guardian_invite_email(link: str) -> tuple[str, str, str]:
    """Return (subject, html, text) for guardian invite."""
    subject = "Guardian Link Invitation — AI Digital Tutor"
    title = "Parent & Guardian Invitation"
    subtitle = "Track and support your student's learning progress"

    content_html = f"""
    <p style="margin-top: 0; font-size: 16px; color: #1e293b; font-weight: 600;">Hello! 👨‍👩‍👧‍👦</p>
    <p style="color: #475569; margin-bottom: 28px;">You have been invited to connect as a Parent/Guardian on AI Digital Tutor. Connecting gives you real-time visibility into learning milestones, quiz scores, and weekly activity digests.</p>
    
    <div style="text-align: center; margin: 32px 0;">
        <a href="{link}" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #ffffff; text-decoration: none; padding: 16px 36px; border-radius: 12px; font-weight: 700; font-size: 16px; display: inline-block; box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);">Accept Invitation &rarr;</a>
    </div>
    
    <p style="color: #64748b; font-size: 13px; margin-top: 24px; word-break: break-all;">
        Or copy and paste this link: <span style="color: #10b981;">{link}</span>
    </p>
    """

    text = f"Guardian Invitation on AI Digital Tutor:\n\nAccept invitation link: {link}"
    html = _base_email_wrapper(title, subtitle, content_html)
    return subject, html, text


def weekly_digest_email(student_name: str, stats: dict) -> tuple[str, str, str]:
    """Return (subject, html, text) for weekly digest report."""
    subject = f"📊 Weekly Learning Digest for {student_name}"
    title = f"Weekly Report: {student_name}"
    subtitle = "Here is a snapshot of learning performance this week"

    quizzes = stats.get('quizzes', 0)
    streak = stats.get('streak', 0)
    mastery = stats.get('mastery', 0)

    content_html = f"""
    <p style="margin-top: 0; font-size: 16px; color: #1e293b; font-weight: 600;">Great progress this week! 🎉</p>
    <p style="color: #475569; margin-bottom: 24px;">Here is the summary of learning activity for <strong>{student_name}</strong>:</p>
    
    <!-- 3 Card Grid -->
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin: 24px 0;">
        <tr>
            <td width="33%" style="padding: 12px; background: #f8fafc; border-radius: 12px; text-align: center; border: 1px solid #e2e8f0;">
                <div style="font-size: 28px; font-weight: 800; color: #4f46e5;">{quizzes}</div>
                <div style="font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin-top: 4px;">Quizzes</div>
            </td>
            <td width="3%" style="width: 3%;"></td>
            <td width="33%" style="padding: 12px; background: #f8fafc; border-radius: 12px; text-align: center; border: 1px solid #e2e8f0;">
                <div style="font-size: 28px; font-weight: 800; color: #f59e0b;">{streak}🔥</div>
                <div style="font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin-top: 4px;">Day Streak</div>
            </td>
            <td width="3%" style="width: 3%;"></td>
            <td width="33%" style="padding: 12px; background: #f8fafc; border-radius: 12px; text-align: center; border: 1px solid #e2e8f0;">
                <div style="font-size: 28px; font-weight: 800; color: #10b981;">{mastery}%</div>
                <div style="font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; margin-top: 4px;">Mastery</div>
            </td>
        </tr>
    </table>
    
    <div style="text-align: center; margin: 32px 0 16px 0;">
        <a href="https://ai-digital-tutor.vercel.app/guardian" style="background: #1e293b; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 10px; font-weight: 600; font-size: 14px; display: inline-block;">View Guardian Dashboard &rarr;</a>
    </div>
    """

    text = f"Weekly Progress Report for {student_name}\n\nQuizzes Completed: {quizzes}\nCurrent Streak: {streak} days\nMastery Level: {mastery}%"
    html = _base_email_wrapper(title, subtitle, content_html)
    return subject, html, text
