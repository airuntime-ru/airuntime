import smtplib
from email.message import EmailMessage
from pathlib import Path

from src.core.config import settings

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "brand" / "logo-mark.png"
LOGO_CID = "airuntime-logo"


def send_email(*, to: str, subject: str, plain: str, html: str | None = None, embed_logo: bool = True) -> bool:
    if not settings.smtp_host:
        return False

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(plain)

    if html:
        message.add_alternative(html, subtype="html")
        if embed_logo and LOGO_PATH.exists():
            html_part = message.get_payload()[-1]
            with LOGO_PATH.open("rb") as logo_file:
                html_part.add_related(
                    logo_file.read(),
                    maintype="image",
                    subtype="png",
                    cid=f"<{LOGO_CID}>",
                )

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
    return True


def send_branded_email(*, to: str, subject: str, plain: str, html: str) -> bool:
    return send_email(to=to, subject=subject, plain=plain, html=html, embed_logo=True)
