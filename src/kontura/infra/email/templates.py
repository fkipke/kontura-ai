from __future__ import annotations


def build_verification_email(
    *, recipient_email: str, verification_url: str
) -> tuple[str, str, str]:
    """Returns (subject, body_text, body_html)."""
    subject = "E-Mail-Adresse bestätigen — Kontura"
    body_text = f"""Willkommen bei Kontura,

bitte bestätige deine E-Mail-Adresse, indem du den folgenden Link öffnest:

{verification_url}

Der Link ist 24 Stunden gültig.

Falls du dich nicht bei Kontura registriert hast, ignoriere diese E-Mail.

— Kontura
"""
    body_html = f"""<!DOCTYPE html>
<html>
<body
  style="
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    max-width: 520px;
    margin: 40px auto;
    color: #111;
  "
>
  <h2 style="font-weight: 600; letter-spacing: -0.01em;">Willkommen bei Kontura</h2>
  <p>Bitte bestätige deine E-Mail-Adresse:</p>
  <p style="margin: 24px 0;">
    <a
      href="{verification_url}"
      style="
        display: inline-block;
        padding: 12px 20px;
        background: #4f46e5;
        color: white;
        text-decoration: none;
        border-radius: 8px;
        font-weight: 500;
      "
    >
      E-Mail-Adresse bestätigen
    </a>
  </p>
  <p style="color: #666; font-size: 14px;">
    Der Link ist 24 Stunden gültig. Falls du dich nicht registriert hast, ignoriere diese E-Mail.
  </p>
</body>
</html>
"""
    return subject, body_text, body_html
