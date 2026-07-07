from __future__ import annotations

from dataclasses import dataclass

from src.core.config import settings

LOGO_CID = "airuntime-logo"

_COLORS = {
    "bg": "#0a0d12",
    "card": "#12161f",
    "border": "rgba(255,255,255,0.12)",
    "cloud": "#f4f7fb",
    "mist": "#c8d0dc",
    "stone": "#8b95a5",
    "sky": "#5eb8ff",
    "cyan": "#4ee0d8",
    "code_bg": "rgba(94,184,255,0.08)",
    "code_border": "rgba(94,184,255,0.28)",
}


@dataclass(frozen=True)
class EmailContent:
    subject: str
    plain: str
    html: str


def _layout(*, title: str, body_html: str, footer: str) -> str:
    frontend_url = settings.resolved_frontend_url
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="color-scheme" content="dark" />
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background:{_COLORS["bg"]};font-family:Inter,'Segoe UI',Roboto,Arial,sans-serif;color:{_COLORS["cloud"]};">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:{_COLORS["bg"]};">
    <tr>
      <td align="center" style="padding:40px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:{_COLORS["card"]};border:1px solid {_COLORS["border"]};border-radius:24px;overflow:hidden;">
          <tr>
            <td style="padding:36px 32px 20px;text-align:center;background:linear-gradient(180deg,rgba(94,184,255,0.08) 0%,transparent 100%);">
              <img src="cid:{LOGO_CID}" width="64" height="64" alt="AIRuntime" style="display:block;margin:0 auto;border:0;" />
              <p style="margin:14px 0 0;font-size:11px;letter-spacing:0.34em;color:{_COLORS["sky"]};font-weight:600;">AIRUNTIME</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 32px 12px;">
              <h1 style="margin:0;font-size:24px;line-height:1.3;font-weight:600;color:{_COLORS["cloud"]};text-align:center;">{title}</h1>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 32px 28px;color:{_COLORS["mist"]};font-size:15px;line-height:1.65;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="padding:0 32px 28px;">
              <p style="margin:0;font-size:12px;line-height:1.6;color:{_COLORS["stone"]};text-align:center;">{footer}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 32px 24px;border-top:1px solid {_COLORS["border"]};text-align:center;">
              <a href="{frontend_url}" style="font-size:12px;color:{_COLORS["sky"]};text-decoration:none;">{frontend_url.replace("https://", "").replace("http://", "")}</a>
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
        f'<tr><td align="center" style="border-radius:12px;background:{_COLORS["sky"]};">'
        f'<a href="{href}" style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:600;'
        f'color:{_COLORS["bg"]};text-decoration:none;border-radius:12px;">{label}</a>'
        f"</td></tr></table>"
    )


def _code_block(code: str) -> str:
    return (
        f'<div style="margin:24px 0;padding:22px 16px;text-align:center;border-radius:16px;'
        f'background:{_COLORS["code_bg"]};border:1px solid {_COLORS["code_border"]};">'
        f'<span style="font-size:36px;font-weight:700;letter-spacing:0.38em;color:{_COLORS["cloud"]};'
        f"font-family:ui-monospace,'JetBrains Mono',Consolas,monospace;\">{code}</span>"
        f"</div>"
    )


def login_code_email(*, code: str, minutes: int) -> EmailContent:
    subject = "Код входа в AIRuntime"
    plain = (
        f"Ваш код для входа в AIRuntime: {code}\n\n"
        f"Код действует {minutes} минут.\n"
        "Если вы не запрашивали вход — просто проигнорируйте это письмо."
    )
    body = (
        "<p style='margin:0 0 12px;text-align:center;'>Используйте этот код, чтобы войти в аккаунт.</p>"
        f"{_code_block(code)}"
        f"<p style='margin:0;text-align:center;'>Код действует <strong style='color:{_COLORS['cloud']};'>{minutes} минут</strong>.</p>"
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
        f"<p style='margin:16px 0 0;font-size:13px;text-align:center;color:{_COLORS['stone']};'>"
        f"Или скопируйте ссылку:<br><span style='color:{_COLORS['mist']};word-break:break-all;'>{verify_url}</span></p>"
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
        f"<p style='margin:16px 0 0;font-size:13px;text-align:center;color:{_COLORS['stone']};'>"
        f"Если это были не вы, просто проигнорируйте письмо.</p>"
    )
    html = _layout(
        title="Сброс пароля",
        body_html=body,
        footer="Ссылка действует 15 минут.",
    )
    return EmailContent(subject=subject, plain=plain, html=html)
