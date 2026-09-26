"""Fetch raw evidence for the 4 downgraded cases to verify capture attribution."""
from __future__ import annotations
import asyncio, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from student_agent.config import Settings

CASES = {
    "L3B_CASE_012": "44a03ff139461361ec4cce7949663c2f",
    "L3B_CASE_071": "676e40056867189a1b3599f3e646f421",
}
TOOLS = ["get_customer_history", "get_order", "get_order_items", "get_payment_timeline"]

async def main() -> None:
    s = Settings.load(ROOT)
    h = {"Authorization": f"Bearer {s.team_api_key}"}
    out = {}
    timeout = httpx2.Timeout(90.0, connect=30.0)
    async with httpx2.AsyncClient(headers=h, timeout=timeout) as c:
        async with streamable_http_client(s.mcp_endpoint, http_client=c) as (r, w):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                for cid, oid in CASES.items():
                    out[cid] = {}
                    for t in TOOLS:
                        args = {"case_id": cid}
                        if t == "get_customer_history":
                            inp = json.loads((ROOT / f"inputs/{cid}.json").read_text(encoding="utf-8"))
                            args["customer_unique_id"] = inp.get("customer_unique_id_hint") or ""
                        else:
                            args["order_id"] = oid
                        try:
                            res = await sess.call_tool(t, arguments=args)
                            txt = "".join(b.text for b in res.content if getattr(b, "text", None))
                            out[cid][t] = {"is_error": getattr(res, "is_error", None), "text": txt}
                        except BaseException as e:
                            out[cid][t] = {"is_error": True, "text": repr(e)[:200]}
    (ROOT / "tools/_o_probe2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ok")

asyncio.run(main())
