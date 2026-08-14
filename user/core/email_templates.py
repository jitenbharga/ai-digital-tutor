def verification_email(link: str):
    subject = "Verify your Digital Tutor account"
    html = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
            <h1 style="color: #2563eb;">Welcome to Digital Tutor!</h1>
            <p>Please verify your email address by clicking the link below:</p>
            <p style="text-align: center; margin: 32px 0;">
                <a href="{link}" style="background: #2563eb; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600;">
                    Verify Email
                </a>
            </p>
            <p style="color: #666; font-size: 14px;">This link expires in 24 hours. If you didn't create an account, you can ignore this email.</p>
        </div>
    </body>
    </html>
    """
    text = f"Welcome to Digital Tutor!\n\nVerify your email: {link}\n\nThis link expires in 24 hours."
    return subject, html, text


def password_reset_email(link: str):
    subject = "Reset your Digital Tutor password"
    html = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 24px;">
            <h1 style="color: #2563eb;">Password Reset Request</h1>
            <p>You requested a password reset. Click the link below to set a new password:</p>
            <p style="text-align: center; margin: 32px 0;">
                <a href="{link}" style="background: #2563eb; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-weight: 600;">
                    Reset Password
                </a>
            </p>
            <p style="color: #666; font-size: 14px;">This link expires in 1 hour. If you didn't request this, you can ignore this email.</p>
        </div>
    </body>
    </html>
    """
    text = f"Password Reset Request\n\nReset your password: {link}\n\nThis link expires in 1 hour."
    return subject, html, text