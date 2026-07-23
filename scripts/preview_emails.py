#!/usr/bin/env python3
"""Local transactional email preview — renders HTML/text without sending.

From repo root:

  $env:PYTHONPATH='backend'  # PowerShell
  python -m scripts.preview_emails --open

Writes files under backend/.email-preview/ (gitignored). Does not touch SMTP.
"""

from __future__ import annotations

import argparse
import html
import webbrowser
from pathlib import Path

from src.services.email_templates import list_template_previews

OUT_DIR = Path(__file__).resolve().parents[1] / "backend" / ".email-preview"


def _index(items: list[dict[str, object]]) -> str:
    links = "\n".join(
        f'<li><a href="{html.escape(str(item["id"]))}.html">{html.escape(str(item["id"]))}</a>'
        f" — {html.escape(str(item['subject']))}</li>"
        for item in items
    )
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"/><title>AIRuntime email preview</title>
<style>
body{{font-family:Arial,Helvetica,sans-serif;margin:24px;background:#F4F8FD;color:#081426}}
a{{color:#2F7CFF}}
</style></head><body>
<h1>AIRuntime email preview</h1>
<p>Локальный рендер без SMTP. Desktop и mobile рядом на странице шаблона.</p>
<ul>{links}</ul>
</body></html>"""


def _wrap_preview(template_id: str, subject: str, body_html: str, plain: str) -> str:
    safe_plain = html.escape(plain)
    srcdoc = html.escape(body_html, quote=True)
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"/><title>{html.escape(subject)}</title>
<style>
body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:#e8eef6;color:#081426}}
header{{padding:12px 16px;background:#081426;color:#fff}}
.grid{{display:grid;grid-template-columns:1fr 360px;gap:12px;padding:12px}}
.pane{{background:#fff;border:1px solid #D9E5F3;border-radius:8px;overflow:hidden}}
.pane h2{{margin:0;padding:10px 12px;font-size:13px;border-bottom:1px solid #D9E5F3;background:#F4F8FD}}
iframe{{width:100%;height:780px;border:0}}
.mobile iframe{{width:320px;margin:0 auto;display:block}}
pre{{margin:0;padding:12px;white-space:pre-wrap;font-size:13px;line-height:1.45}}
@media (max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<header><strong>{html.escape(template_id)}</strong> — {html.escape(subject)}</header>
<div class="grid">
  <div class="pane"><h2>Desktop ~600px</h2><iframe srcdoc="{srcdoc}"></iframe></div>
  <div class="pane mobile"><h2>Mobile 320px</h2><iframe srcdoc="{srcdoc}"></iframe></div>
</div>
<div class="pane" style="margin:0 12px 16px"><h2>Plain text</h2><pre>{safe_plain}</pre></div>
<p style="padding:0 16px 24px"><a href="index.html">← все шаблоны</a></p>
</body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview AIRuntime transactional emails locally")
    parser.add_argument("--id", help="Render a single template id")
    parser.add_argument("--open", action="store_true", help="Open index in the browser")
    parser.add_argument(
        "--cid",
        action="store_true",
        help="Keep cid: logo references (default uses absolute FRONTEND_URL for browser preview)",
    )
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = list_template_previews(use_cid=args.cid)
    if args.id:
        samples = [item for item in samples if item["id"] == args.id]
        if not samples:
            raise SystemExit(f"Unknown template id: {args.id}")

    (OUT_DIR / "index.html").write_text(_index(samples), encoding="utf-8")
    for item in samples:
        page = _wrap_preview(
            str(item["id"]), str(item["subject"]), str(item["html"]), str(item["plain"])
        )
        (OUT_DIR / f"{item['id']}.html").write_text(page, encoding="utf-8")
        (OUT_DIR / f"{item['id']}.txt").write_text(str(item["plain"]), encoding="utf-8")
        (OUT_DIR / f"{item['id']}.raw.html").write_text(str(item["html"]), encoding="utf-8")

    print(f"Wrote {len(samples)} templates to {OUT_DIR}")
    if args.open:
        webbrowser.open((OUT_DIR / "index.html").as_uri())


if __name__ == "__main__":
    main()
