"""Optional invite emails over plain SMTP (no extra packages, no vendor lock-in).

Works with Gmail (app password), Brevo, Mailgun, SendGrid, Resend, Amazon SES,
Zoho... anything that offers SMTP credentials. If SMTP isn't configured the
app still works: the UI hands the user a link to share themselves.
"""
import smtplib
from email.message import EmailMessage
from html import escape
from flask import current_app


def mail_configured():
    c = current_app.config
    return bool(c.get("SMTP_HOST") and c.get("SMTP_FROM"))


def send_invite_email(to_email, inviter_name, household_name, link, code):
    """Returns (ok: bool, error: str | None). Never raises."""
    if not mail_configured():
        return False, "Email isn't set up on the server yet"

    c = current_app.config
    subject = f"{inviter_name} invited you to {household_name} on ShelfWise"
    text = (
        f"{inviter_name} invited you to share the \"{household_name}\" kitchen on ShelfWise.\n\n"
        f"Join here: {link}\n\n"
        f"Or sign in and enter this household code: {code}\n\n"
        "This link works once and expires soon. If you weren't expecting it, you can ignore this email."
    )
    html = f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;max-width:480px;margin:auto;color:#12291d">
  <h2 style="margin:0 0 8px">You're invited to <span style="color:#2a7a1c">{escape(household_name)}</span></h2>
  <p><b>{escape(inviter_name)}</b> wants to share their kitchen with you on ShelfWise, so you can both see
  what's about to expire and waste less food.</p>
  <p style="margin:24px 0"><a href="{escape(link)}"
     style="background:#2c8c17;color:#fff;text-decoration:none;padding:12px 22px;border-radius:999px;font-weight:700">
     Join {escape(household_name)}</a></p>
  <p style="font-size:13px;color:#4b6356">Or sign in and enter the household code <b>{escape(code)}</b>.<br>
  This link works once and expires soon.</p>
</div>"""

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = c["SMTP_FROM"]
    msg["To"] = to_email
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    try:
        port = c["SMTP_PORT"]
        if port == 465:
            server = smtplib.SMTP_SSL(c["SMTP_HOST"], port, timeout=10)
        else:
            server = smtplib.SMTP(c["SMTP_HOST"], port, timeout=10)
            server.starttls()
        with server:
            if c.get("SMTP_USER"):
                server.login(c["SMTP_USER"], c["SMTP_PASSWORD"])
            server.send_message(msg)
        return True, None
    except smtplib.SMTPAuthenticationError:
        current_app.logger.exception("SMTP login failed")
        return False, "The email server rejected the username or password"
    except Exception as e:  # network, TLS, refused recipient, ...
        current_app.logger.exception("Sending invite email failed")
        return False, f"Couldn't send the email ({type(e).__name__})"
