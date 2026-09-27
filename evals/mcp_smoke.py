"""Smoke test: start the MCP server over stdio like Claude Desktop does, list tools, call them.

    python -m evals.mcp_smoke
"""

import asyncio
import sys

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "redflag.mcp_server"])
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        print("tools:", [t.name for t in (await s.list_tools()).tools])
        res = await s.call_tool("ask_prospectus", {"doc": "madhur_steel",
                                                   "question": "What were current borrowings as at March 31, 2026 in the restated balance sheet?"})
        print("ask:", " ".join(res.content[0].text.split())[:240])
        res = await s.call_tool("read_page", {"doc": "madhur_steel", "page": 85})
        print("page 85 contains 18,628.02:", "18,628.02" in res.content[0].text)
        res = await s.call_tool("ask_prospectus", {"doc": "nope", "question": "x"})
        print("unknown doc is an error:", res.is_error)


if __name__ == "__main__":
    asyncio.run(main())
