from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from .contracts import Contracts


def _attr(obj: Any, *names: str) -> Any:
    """Read the first present attribute, tolerating camelCase/snake_case drift."""
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return None


class EvidenceGateway:
    def __init__(self, session: ClientSession, contracts: Contracts) -> None:
        self._session = session
        self._contracts = contracts

    async def list_tools(self) -> list[str]:
        response = await self._session.list_tools()
        return sorted(tool.name for tool in response.tools)

    async def call(self, tool_name: str, *, case_id: str, **arguments: str) -> dict[str, Any]:
        payload = {"case_id": case_id, **arguments}
        result = await self._session.call_tool(tool_name, arguments=payload)
        if _attr(result, "is_error", "isError"):
            message = " ".join(
                block.text for block in result.content if getattr(block, "text", None)
            )
            raise RuntimeError(f"MCP tool {tool_name} failed: {message or 'unknown error'}")
        evidence = _attr(result, "structured_content", "structuredContent")
        if evidence is None:
            text_blocks = [block.text for block in result.content if getattr(block, "text", None)]
            if len(text_blocks) != 1:
                raise ValueError(f"MCP tool {tool_name} did not return one evidence object")
            evidence = json.loads(text_blocks[0])
        self._contracts.validate_evidence(evidence, f"MCP tool {tool_name}")
        return evidence


@asynccontextmanager
async def connect_gateway(
    endpoint: str, team_api_key: str, contracts: Contracts, attempts: int = 8
) -> AsyncIterator[EvidenceGateway]:
    """Open one audited session, retrying only the connect handshake.

    Retrying here is safe: a failed handshake never reached a tool call, so no
    extra MCP call is audited. Calls inside the session are never retried; the
    caller reconnects and replays the case if a session dies mid-run.
    """
    headers = {"Authorization": f"Bearer {team_api_key}"}
    timeout = httpx2.Timeout(300.0, connect=45.0, write=45.0, read=300.0, pool=45.0)
    last: BaseException | None = None
    for attempt in range(attempts):
        stack = AsyncExitStack()
        try:
            http_client = await stack.enter_async_context(
                httpx2.AsyncClient(headers=headers, timeout=timeout)
            )
            read_stream, write_stream = await stack.enter_async_context(
                streamable_http_client(endpoint, http_client=http_client)
            )
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
        except BaseException as exc:  # noqa: BLE001 - connect retry
            last = exc
            await stack.aclose()
            if attempt + 1 >= attempts:
                break
            await asyncio.sleep(min(2.0 * (attempt + 1), 10.0))
            continue
        try:
            yield EvidenceGateway(session, contracts)
        finally:
            await stack.aclose()
        return
    raise RuntimeError(f"could not connect to MCP gateway after {attempts} attempts: {last!r}")
