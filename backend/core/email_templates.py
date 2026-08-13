"""
HTML & Plaintext email templates for AI Tutor notifications.
"""


def verification_email(link: str) -> tuple[str, str, str]:
    """Return (subject, html, text) for email verification."""
    subject = "Verify your email — AI Digital Tutor"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px;">
        <div style="max-width: 560px; margin: 0 auto; background: #ffffff; padding: 32px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <h2 style="color: #4f46e5; margin-top: 0;">Welcome to AI Digital Tutor!</h2>
            <p style="color: #334155; font-size: 16px; line-height: 1.5;">Please confirm your email address to activate your account and access your personalized learning journey.</p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{link}" style="background-color: #4f46e5; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; display: inline-block;">Verify Email Address</a>
            </div>
            <p style="color: #64748b; font-size: 14px;">Or copy and paste this link in your browser:</p>
            <p style="color: #64748b; font-size: 12px; word-break: break-all;">{link}</p>
        </div>
    </body>
    </html>
    """
    text = f"Welcome to AI Digital Tutor!\n\nPlease verify your email by opening this link: {link}"
    return subject, html, text


def password_reset_email(link: str) -> tuple[str, str, str]:
    """Return (subject, html, text) for password reset."""
    subject = "Reset your password — AI Digital Tutor"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px;">
        <div style="max-width: 560px; margin: 0 auto; background: #ffffff; padding: 32px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <h2 style="color: #4f46e5; margin-top: 0;">Reset Your Password</h2>
            <p style="color: #334155; font-size: 16px; line-height: 1.5;">We received a request to reset your password. Click the button below to choose a new password.</p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{link}" style="background-color: #4f46e5; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; display: inline-block;">Reset Password</a>
            </div>
            <p style="color: #64748b; font-size: 14px;">If you did not request this, you can safely ignore this email.</p>
            <p style="color: #64748b; font-size: 12px; word-break: break-all;">{link}</p>
        </div>
    </body>
    </html>
    """
    text = f"Reset your password on AI Digital Tutor:\n\nOpen this link: {link}"
    return subject, html, text


def guardian_invite_email(link: str) -> tuple[str, str, str]:
    """Return (subject, html, text) for guardian invite."""
    subject = "Guardian Invitation — AI Digital Tutor"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px;">
        <div style="max-width: 560px; margin: 0 auto; background: #ffffff; padding: 32px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <h2 style="color: #4f46e5; margin-top: 0;">Guardian Account Invitation</h2>
            <p style="color: #334155; font-size: 16px; line-height: 1.5;">You have been invited to link as a parent/guardian to monitor student learning progress on AI Digital Tutor.</p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{link}" style="background-color: #4f46e5; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; display: inline-block;">Accept Invitation</a>
            </div>
            <p style="color: #64748b; font-size: 12px; word-break: break-all;">{link}</p>
        </div>
    </body>
    </html>
    """
    text = f"Guardian Invitation:\n\nAccept invitation link: {link}"
    return subject, html, text


def weekly_digest_email(student_name: str, stats: dict) -> tuple[str, str, str]:
    """Return (subject, html, text) for weekly digest report."""
    subject = f"Weekly Learning Progress Report for {student_name}"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px;">
        <div style="max-width: 560px; margin: 0 auto; background: #ffffff; padding: 32px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <h2 style="color: #4f46e5; margin-top: 0;">Weekly Progress Report</h2>
            <p style="color: #334155; font-size: 16px;">Student: <strong>{student_name}</strong></p>
            <ul style="color: #334155; font-size: 15px; line-height: 1.8;">
                <li>Quizzes Completed: {stats.get('quizzes', 0)}</li>
                <li>Current Streak: {stats.get('streak', 0)} days</li>
                <li>Mastery Level: {stats.get('mastery', 0)}%</li>
            </ul>
        </div>
    </body>
    </html>
    """
    text = f"Weekly Progress Report for {student_name}\n\nQuizzes: {stats.get('quizzes', 0)}\nStreak: {stats.get('streak', 0)} days\nMastery: {stats.get('mastery', 0)}%"
    return subject, html, text
