from __future__ import annotations

from dataclasses import dataclass

from src.core.config import settings

LOGO_CID = "airuntime-logo"

_COLORS = {
    "page": "#f4f9ff",
    "card": "#ffffff",
    "ink": "#081426",
    "muted": "#627086",
    "soft": "#8a96a8",
    "border": "#dcebf8",
    "sky": "#2388ff",
    "cyan": "#18c7ca",
    "mint": "#6ee7b7",
    "code_bg": "#f1f8ff",
}


@dataclass(frozen=True)
class EmailContent:
    subject: str
    plain: str
    html: str


def _layout(*, title: str, body_html: str, footer: str) -> str:
    frontend_url = settings.resolved_frontend_url
    short_url = frontend_url.replace("https://", "").replace("http://", "")
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="light" />
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:{_COLORS["page"]};font-family:Inter,'Segoe UI',Roboto,Arial,sans-serif;color:{_COLORS["ink"]};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{_COLORS["page"]};">
    <tr>
      <td align="center" style="padding:40px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background:{_COLORS["card"]};border:1px solid {_COLORS["border"]};border-radius:18px;overflow:hidden;box-shadow:0 18px 54px rgba(56,112,180,0.14);">
          <tr>
            <td style="padding:34px 32px 18px;text-align:center;background:linear-gradient(135deg,#ffffff 0%,#f1f8ff 58%,#ecfffb 100%);">
              <img src="cid:{LOGO_CID}" width="64" height="64" alt="AIRuntime" style="display:block;margin:0 auto;border:0;" />
              <p style="margin:14px 0 0;font-size:11px;letter-spacing:0.34em;color:{_COLORS["sky"]};font-weight:700;">AIRUNTIME</p>
            </td>
          </tr>
          <tr>
            <td style="padding:10px 32px 8px;">
              <h1 style="margin:0;font-size:26px;line-height:1.28;font-weight:700;color:{_COLORS["ink"]};text-align:center;">{title}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 32px 30px;color:{_COLORS["muted"]};font-size:15px;line-height:1.65;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:0 32px 28px;">
              <p style="margin:0;font-size:12px;line-height:1.6;color:{_COLORS["soft"]};text-align:center;">{footer}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 32px 24px;border-top:1px solid {_COLORS["border"]};text-align:center;background:#fbfdff;">
              <a href="{frontend_url}" style="font-size:12px;color:{_COLORS["sky"]};text-decoration:none;">{short_url}</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _button(label: str, href: str) -> str:
    return (
        f'<table role="presentation" cellspacing="0" cellpadding="0" style="margin:24px auto 8px;">'
        f'<tr><td align="center" style="border-radius:10px;background:{_COLORS["sky"]};">'
        f'<a href="{href}" style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:700;'
        f'color:#ffffff;text-decoration:none;border-radius:10px;">{label}</a>'
        f"</td></tr></table>"
    )


def _code_block(code: str) -> str:
    return (
        f'<div style="margin:24px 0;padding:22px 16px;text-align:center;border-radius:14px;'
        f'background:{_COLORS["code_bg"]};border:1px solid {_COLORS["border"]};">'
        f'<span style="font-size:36px;font-weight:800;letter-spacing:0.34em;color:{_COLORS["ink"]};'
        f"font-family:ui-monospace,'JetBrains Mono',Consolas,monospace;\">{code}</span>"
        f"</div>"
    )


def login_code_email(*, code: str, minutes: int) -> EmailContent:
    subject = "Код входа в AIRuntime"
    plain = (
        f"Ваш код для входа в AIRuntime: {code}\n\n"
        f"Код действует {minutes} минут.\n"
        "Если вы не запрашивали вход, просто проигнорируйте это письмо."
    )
    body = (
        "<p style='margin:0 0 12px;text-align:center;'>Используйте этот код, чтобы войти в аккаунт.</p>"
        f"{_code_block(code)}"
        f"<p style='margin:0;text-align:center;'>Код действует <strong style='color:{_COLORS['ink']};'>{minutes} минут</strong>.</p>"
    )
    html = _layout(
        title="Вход в AIRuntime",
        body_html=body,
        footer="Если вы не запрашивали вход, ничего делать не нужно.",
    )
    return EmailContent(subject=subject, plain=plain, html=html)


def verify_email(*, verify_url: str) -> EmailContent:
    subject = "Подтвердите почту в AIRuntime"
    plain = f"Подтвердите адрес почты: {verify_url}"
    body = (
        "<p style='margin:0 0 8px;text-align:center;'>Остался один шаг — подтвердите адрес почты.</p>"
        f"{_button('Подтвердить почту', verify_url)}"
        f"<p style='margin:16px 0 0;font-size:13px;text-align:center;color:{_COLORS['soft']};'>"
        f"Или скопируйте ссылку:<br><span style='color:{_COLORS['muted']};word-break:break-all;'>{verify_url}</span></p>"
    )
    html = _layout(
        title="Подтверждение почты",
        body_html=body,
        footer="Ссылка действует 24 часа.",
    )
    return EmailContent(subject=subject, plain=plain, html=html)


def password_reset_email(*, reset_url: str) -> EmailContent:
    subject = "Сброс пароля AIRuntime"
    plain = f"Сбросьте пароль по ссылке: {reset_url}"
    body = (
        "<p style='margin:0 0 8px;text-align:center;'>Вы запросили сброс пароля.</p>"
        f"{_button('Сбросить пароль', reset_url)}"
        f"<p style='margin:16px 0 0;font-size:13px;text-align:center;color:{_COLORS['soft']};'>"
        f"Если это были не вы, просто проигнорируйте письмо.</p>"
    )
    html = _layout(
        title="Сброс пароля",
        body_html=body,
        footer="Ссылка действует 15 минут.",
    )
    return EmailContent(subject=subject, plain=plain, html=html)
