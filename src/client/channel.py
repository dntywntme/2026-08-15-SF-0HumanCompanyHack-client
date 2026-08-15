"""The wire between client and firm: GitHub Issues, cross-repository.

No phone, no webhook receiver, no vendor. The client opens an Issue on the
firm's repository; the firm's Actions run on ``issues.opened`` and reply as an
issue comment. Both directions are public and permanently auditable -- you can
read every order the company ever took.

The boundary is enforced by token scope, not by convention: the credential used
here is expected to carry Issues:write on the firm repo and nothing else, so a
compromised client can place an order but cannot push code, alter a workflow, or
merge anything.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

GITHUB_API = "https://api.github.com"
DEFAULT_FIRM_REPO = "dntywntme/2026-08-15-SF-0HumanCompanyHack-firm"

# A work order is fenced JSON inside the issue body. The firm parses the fence
# and validates it; free prose around it is never interpreted.
ORDER_FENCE = "```json"


class ChannelError(RuntimeError):
    """The channel failed. Callers degrade; they do not crash."""


def _request(method: str, path: str, token: str, body: dict | None = None) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{GITHUB_API}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "broker-client",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        raise ChannelError(f"{method} {path} -> HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ChannelError(f"{method} {path} -> {type(exc).__name__}") from exc


def render_order_body(order_payload: dict[str, Any], note: str = "") -> str:
    """Issue body: a human-readable note plus the machine-readable order."""
    fenced = f"{ORDER_FENCE}\n{json.dumps(order_payload, indent=2, sort_keys=True)}\n```"
    header = note.strip() or "Work order from the client agent."
    return f"{header}\n\n{fenced}\n"


def extract_order(body: str) -> dict[str, Any]:
    """Pull the fenced JSON back out of an issue body.

    Deliberately strict: no fence, no order. Prose outside the fence is never
    parsed, so an issue that only *talks about* an order is not one.
    """
    start = body.find(ORDER_FENCE)
    if start == -1:
        raise ChannelError("no fenced json order in issue body")
    start += len(ORDER_FENCE)
    end = body.find("```", start)
    if end == -1:
        raise ChannelError("unterminated json fence in issue body")
    try:
        parsed = json.loads(body[start:end])
    except json.JSONDecodeError as exc:
        raise ChannelError(f"order fence is not valid json: {exc.msg}") from exc
    if not isinstance(parsed, dict):
        raise ChannelError(f"order must be a json object, got {type(parsed).__name__}")
    return parsed


def submit_order(
    order_payload: dict[str, Any],
    *,
    token: str | None = None,
    repo: str | None = None,
    title: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Open an issue on the firm's repo. Returns the created issue."""
    token = token or os.environ.get("CLIENT_GITHUB_TOKEN", "")
    if not token:
        raise ChannelError("CLIENT_GITHUB_TOKEN is not set")
    repo = repo or os.environ.get("FIRM_REPO", DEFAULT_FIRM_REPO)
    order_id = order_payload.get("id", "order")
    return _request(
        "POST",
        f"/repos/{repo}/issues",
        token,
        {
            "title": title or f"order: {order_id}",
            "body": render_order_body(order_payload, note),
            "labels": ["work-order"],
        },
    )


def read_replies(
    issue_number: int, *, token: str | None = None, repo: str | None = None
) -> list[dict[str, Any]]:
    """Read the firm's replies. Polling, because a static site cannot receive."""
    token = token or os.environ.get("CLIENT_GITHUB_TOKEN", "")
    if not token:
        raise ChannelError("CLIENT_GITHUB_TOKEN is not set")
    repo = repo or os.environ.get("FIRM_REPO", DEFAULT_FIRM_REPO)
    result = _request("GET", f"/repos/{repo}/issues/{issue_number}/comments", token)
    return result if isinstance(result, list) else []
