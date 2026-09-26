"""Probe the competition API for the public score / component breakdown."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx2

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def main() -> None:
    env = load_env()
    key = env.get("COMPETITION_TEAM_API_KEY", "")
    bases = [env.get("COMPETITION_API_URL", "").rstrip("/")]
    bases = [base for base in bases if base]
    paths = [
        "/",
        "/api",
        "/api/health",
        "/api/me",
        "/api/teams/me",
        "/api/l3b",
        "/api/l3b/score",
        "/api/l3b/feedback",
        "/api/score",
        "/api/submissions",
        "/api/l3b/submissions",
        "/api/leaderboard",
        "/api/l3b/leaderboard",
        "/api/results",
        "/api/l3b/results",
    ]
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    with httpx2.Client(headers=headers, timeout=15.0, follow_redirects=True) as client:
        for base in bases:
            for path in paths:
                try:
                    response = client.get(base + path)
                    body = " ".join(response.text.split())[:260]
                    ctype = response.headers.get("content-type", "")[:24]
                    print(f"{response.status_code} {path} [{ctype}] {body}")
                except Exception as exc:  # noqa: BLE001
                    print(f"ERR {path} {type(exc).__name__}: {exc}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
