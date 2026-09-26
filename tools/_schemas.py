import asyncio, json, sys
from pathlib import Path
ROOT = Path(".").resolve(); sys.path.insert(0, str(ROOT/"src"))
from student_agent.config import Settings
from student_agent.contracts import Contracts
from student_agent.mcp_gateway import connect_gateway
async def main():
    s=Settings.load(ROOT); c=Contracts(ROOT/"contracts"/"schemas")
    async with connect_gateway(s.mcp_endpoint, s.team_api_key, c) as g:
        from mcp import ClientSession
        resp = await g._session.list_tools()
        out=[]
        for t in resp.tools:
            sch = t.input_schema or {}
            out.append(f"{t.name} | required={sch.get('required')} | props={json.dumps(sch.get('properties'),ensure_ascii=False)}")
        open("tools/_schemas.txt","w",encoding="utf-8").write("\n".join(out))
        print("wrote", len(out))
asyncio.run(main())
