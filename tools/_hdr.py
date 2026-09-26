import asyncio, json, sys
from pathlib import Path
ROOT = Path(".").resolve(); sys.path.insert(0, str(ROOT/"src"))
from student_agent.config import Settings
from student_agent.contracts import Contracts
from student_agent.mcp_gateway import connect_gateway
async def main():
    s=Settings.load(ROOT); c=Contracts(ROOT/"contracts"/"schemas")
    async with connect_gateway(s.mcp_endpoint, s.team_api_key, c) as g:
        # raw result object
        res = await g._session.call_tool("get_policy", arguments={"case_id":"L3B_CASE_010","policy_version":"EC_POLICY_V2"})
        print("RESULT ATTRS:", [a for a in dir(res) if not a.startswith('_')])
        print("meta:", getattr(res,"meta",None))
        sc = getattr(res,"structured_content",None)
        print("policy 010 late_delivery_seller:", json.dumps((sc or {}).get("data",{}).get("rules",{}).get("late_delivery_seller"), ensure_ascii=False))
        print("policy 010 unavailable_order_paid:", json.dumps((sc or {}).get("data",{}).get("rules",{}).get("unavailable_order_paid"), ensure_ascii=False))
        r2 = await g._session.call_tool("get_order_payments", arguments={"case_id":"L3B_CASE_001","order_id":"af0bbb47f125381ce9f3597dc70ef07b"})
        print("payments 001:", json.dumps(getattr(r2,"structured_content",None), ensure_ascii=False)[:600])
asyncio.run(main())
