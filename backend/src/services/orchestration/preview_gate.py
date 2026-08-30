"""Shared preview acceptance rules — isolated preview has no outbound internet."""

from __future__ import annotations

# External font/style CDNs are unreachable in the preview network; failing on them
# causes endless implementer/replan loops without improving the shipped site.
_EXTERNAL_FONT_CDN_HOSTS = (
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "use.typekit.net",
    "fast.fonts.net",
    "cloud.typography.com",
)


def is_benign_preview_network_error(error: str) -> bool:
    lower = error.lower()
    return any(host in lower for host in _EXTERNAL_FONT_CDN_HOSTS)


def blocking_network_errors(network_errors: list[str]) -> list[str]:
    return [entry for entry in network_errors if not is_benign_preview_network_error(entry)]


def _page_issues_blocking(page: dict) -> list[str]:
    issues: list[str] = []
    if page.get("console_errors"):
        issues.append("console_errors")
    if blocking_network_errors(page.get("network_errors") or []):
        issues.append("network_errors")
    if page.get("overflow_elements"):
        issues.append("overflow")
    if page.get("broken_images"):
        issues.append("broken_images")
    return issues


def preview_passes_validation(preview_result: dict) -> bool:
    status = preview_result.get("status")
    if status == "passed":
        return True
    if status != "issues_found":
        return False
    if preview_result.get("fatal_errors"):
        return False
    pages = preview_result.get("pages")
    if not isinstance(pages, list) or not pages:
        return False
    return all(not _page_issues_blocking(page) for page in pages if isinstance(page, dict))
