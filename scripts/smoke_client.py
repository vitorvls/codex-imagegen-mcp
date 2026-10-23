"""Smoke test: starts the server over stdio, lists the tools and calls generate_image.

uv run python scripts/smoke_client.py [args.json]
The JSON holds generate_image's arguments. Without a file, it only lists the tools.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import get_default_environment, stdio_client

ROOT = Path(__file__).resolve().parent.parent
# The MCP client only passes a minimal environment; these variables go explicitly, as in the registration.
PASS = ["CODEX_HOME", "IMAGEGEN_CODEX_JS", "IMAGEGEN_ROOT", "IMAGEGEN_WORKDIR",
        "IMAGEGEN_DENY", "IMAGEGEN_BACKEND", "IMAGEGEN_CODEX_TIMEOUT"]


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "codex_imagegen_mcp.server"], cwd=str(ROOT),
                                   env=get_default_environment() | {k: os.environ[k] for k in PASS if k in os.environ})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            for t in tools.tools:
                print("tool:", t.name, "| params:", list(t.input_schema.get("properties", {})))
            if len(sys.argv) > 1:
                args = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
                res = await s.call_tool("generate_image", args)
                print("error:", res.is_error)
                for c in res.content:
                    print(getattr(c, "text", c))
                if res.structured_content:
                    print(json.dumps(res.structured_content, ensure_ascii=False, indent=2))


asyncio.run(main())
