"""Check whether the gateway errors are team-scoped.

Compares: our key vs no key vs a bogus key, on the tools/list handshake, plus
the competition API for any quota/status field.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import httpx2  # noqa: E402

from student_agent.config import Settings  # noqa: E402


def probe(label: str, key: str | None) -> None:
    settings = Settings.load(ROOT)
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if key is not None:
        headers["Authorization"] = f"Bearer {key}"
    body = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "probe", "version": "1"}}}
    try:
        with httpx2.Client(timeout=45.0) as c:
            r = c.post(settings.mcp_endpoint, headers=headers, json=body)
            print(f"{label}: status={r.status_code} body={r.text[:220]!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"{label}: EXC {type(exc).__name__}: {str(exc)[:160]}")


def main() -> None:
    settings = Settings.load(ROOT)
    probe("our-key", settings.team_api_key)
    probe("bogus-key", "sk-team-000000000000")
    probe("no-key", None)
    with httpx2.Client(timeout=30.0, headers={
        "Authorization": f"Bearer {settings.team_api_key}", "Accept": "application/json"
    }) as c:
        for p in ("/api/v2/me", "/api/v2/competitions", "/api/health"):
            r = c.get("https://n7-competition.pages.dev" + p)
            print(f"api {p}: {r.status_code} {r.text[:200]!r}")


main()
