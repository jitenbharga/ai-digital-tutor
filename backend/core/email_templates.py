"""
Branded HTML email templates for transactional mail (verify / reset).

Email-safe by design: table layout, all styles inline, solid-colour fallbacks
under every gradient (Gmail/Outlook strip <style> blocks and SVG). Colours mirror
the web app's brand scale (indigo/violet) from frontend/tailwind.config.js.

Each builder returns (subject, html, text).
"""
from __future__ import annotations

# Brand tokens (kept in sync with tailwind.config.js `brand` + index.css)
_BRAND = "#4f46e5"          # brand-600 — primary
_BRAND_LIGHT = "#6366f1"    # brand-500
_VIOLET = "#7c3aed"         # gradient end
_ACCENT = "#f97316"         # orange sparkle
_INK = "#0f172a"            # text
_MUTED = "#64748b"          # muted text
_BG = "#eef2ff"             # brand-50 page background
_BORDER = "#e6e9f0"
_APP_NAME = "AI Tutor"


def _layout(*, preheader: str, heading: str, intro: str, cta_label: str,
            cta_url: str, after: str, expiry: str) -> str:
    """Shared responsive, email-client-safe card layout."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light">
<title>{_APP_NAME}</title>
</head>
<body style="margin:0;padding:0;background:{_BG};">
<!-- preheader (hidden inbox preview) -->
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:{_BG};font-size:1px;line-height:1px;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_BG};padding:32px 12px;">
  <tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:#ffffff;border:1px solid {_BORDER};border-radius:16px;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
      <!-- header -->
      <tr>
        <td style="background:{_BRAND};background-image:linear-gradient(135deg,{_BRAND_LIGHT},{_VIOLET});padding:26px 32px;">
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="vertical-align:middle;">
                <table role="presentation" cellpadding="0" cellspacing="0"><tr>
                  <td width="36" height="36" align="center" valign="middle" style="width:36px;height:36px;background:#ffffff;border-radius:10px;font-size:20px;line-height:36px;color:{_BRAND};font-weight:700;">&#10022;</td>
                  <td style="padding-left:12px;color:#ffffff;font-size:20px;font-weight:700;letter-spacing:.2px;">{_APP_NAME}</td>
                </tr></table>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <!-- body -->
      <tr>
        <td style="padding:36px 32px 8px 32px;">
          <h1 style="margin:0 0 12px 0;color:{_INK};font-size:22px;font-weight:700;">{heading}</h1>
          <p style="margin:0 0 24px 0;color:{_MUTED};font-size:15px;line-height:1.6;">{intro}</p>
          <!-- bulletproof CTA -->
          <table role="presentation" cellpadding="0" cellspacing="0"><tr>
            <td align="center" style="border-radius:10px;background:{_BRAND};background-image:linear-gradient(135deg,{_BRAND_LIGHT},{_VIOLET});">
              <a href="{cta_url}" style="display:inline-block;padding:14px 34px;color:#ffffff;font-size:16px;font-weight:600;text-decoration:none;border-radius:10px;">{cta_label}</a>
            </td>
          </tr></table>
          <p style="margin:24px 0 4px 0;color:{_MUTED};font-size:13px;line-height:1.6;">{after}</p>
          <p style="margin:0 0 8px 0;color:{_BRAND};font-size:13px;word-break:break-all;"><a href="{cta_url}" style="color:{_BRAND};text-decoration:underline;">{cta_url}</a></p>
          <p style="margin:20px 0 0 0;color:{_MUTED};font-size:13px;">{expiry}</p>
        </td>
      </tr>
      <!-- divider -->
      <tr><td style="padding:24px 32px 0 32px;"><div style="border-top:1px solid {_BORDER};"></div></td></tr>
      <!-- footer -->
      <tr>
        <td style="padding:16px 32px 32px 32px;">
          <p style="margin:0;color:{_MUTED};font-size:12px;line-height:1.6;">If you didn&#39;t request this, you can safely ignore this email &mdash; no action is needed.</p>
          <p style="margin:10px 0 0 0;color:#94a3b8;font-size:12px;">&copy; {_APP_NAME} &middot; Learn smarter, every day.</p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def verification_email(link: str) -> tuple[str, str, str]:
    subject = f"Verify your email · {_APP_NAME}"
    html = _layout(
        preheader="Confirm your email to activate your account.",
        heading="Confirm your email",
        intro=(
            "Welcome to <strong>AI Tutor</strong>! You&#39;re one click away from your "
            "personalised learning path. Tap the button below to verify your email and "
            "activate your account."
        ),
        cta_label="Verify my email",
        cta_url=link,
        after="Button not working? Copy and paste this link into your browser:",
        expiry="This link expires in 24 hours.",
    )
    text = (
        "Welcome to AI Tutor!\n\n"
        "Confirm your email within 24 hours to activate your account:\n"
        f"{link}\n\n"
        "If you didn't sign up, you can ignore this email."
    )
    return subject, html, text


def password_reset_email(link: str) -> tuple[str, str, str]:
    subject = f"Reset your password · {_APP_NAME}"
    html = _layout(
        preheader="Reset your AI Tutor password.",
        heading="Reset your password",
        intro=(
            "We got a request to reset your <strong>AI Tutor</strong> password. "
            "Tap the button below to choose a new one. Your current password stays "
            "active until you do."
        ),
        cta_label="Reset password",
        cta_url=link,
        after="Button not working? Copy and paste this link into your browser:",
        expiry="This link expires in 1 hour and can be used once.",
    )
    text = (
        "Reset your AI Tutor password.\n\n"
        "Use this link within 1 hour to reset your password:\n"
        f"{link}\n\n"
        "If you didn't request this, you can ignore this email."
    )
    return subject, html, text
