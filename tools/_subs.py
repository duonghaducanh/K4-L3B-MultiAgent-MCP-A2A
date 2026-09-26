"""Check submission quota and our submission history (never prints the key)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import httpx2  # noqa: E402

from score import BASE, client  # noqa: E402


def main() -> None:
    with client() as c:
        comps = c.get(f"{BASE}/api/v2/competitions").json()
        print("competitions:", json.dumps(comps))
        subs = c.get(f"{BASE}/api/v2/me/submissions").json()
        print("my submissions:", json.dumps(subs)[:2000])
        me = c.get(f"{BASE}/api/v2/me").json()
        print("me:", json.dumps(me)[:600])
        lb = c.get(f"{BASE}/api/v2/leaderboard/l3b").json()
        ents = lb.get("entries", [])
        print("leaderboard n:", len(ents))
        for e in ents[:5]:
            print("  ", e.get("rank"), e.get("team_code"), e.get("score"))


if __name__ == "__main__":
    main()
