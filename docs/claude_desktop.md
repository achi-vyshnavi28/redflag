# Using RedFlag from Claude Desktop (MCP)

RedFlag runs as an MCP server, so an analyst can ask Claude about a prospectus and Claude calls RedFlag's tools:
answers come back with a verified page citation (or a decline), and Claude can open the cited page to show the evidence.

## Setup (Windows)
1. Install Claude Desktop (free) and this repo (`pip install -r requirements.txt`, `python -m redflag.setup`, `python -m redflag.index bge`).
2. Open `%APPDATA%\Claude\claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "redflag": {
      "command": "C:\path\to\python.exe",
      "args": ["C:\path\to\redflag\redflag\mcp_server.py"],
      "env": {"GEMINI_API_KEY": "your key"}
    }
  }
}
```
3. Restart Claude Desktop. The tools appear under the tools icon.

## Tools
| Tool | What it does |
|---|---|
| `list_prospectuses` | Companies available |
| `ask_prospectus(doc, question)` | Verified, page-cited answer, or `found=false` |
| `red_flag_memo(doc)` | The red-flag memo, every figure cited |
| `read_page(doc, page)` | Raw page text, to check a citation |

## Try
- "Using RedFlag, what are Madhur Iron & Steel's financial covenants? Show me the page."
- "Compare the three companies' current borrowings as at March 31, 2026, with citations."

Tested with the MCP Python SDK's stdio client (`python -m evals.mcp_smoke`): tools list, a verified answer
(₹18,628.02 lakh, p. 85), page read, and an error for an unknown document.
