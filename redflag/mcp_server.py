"""MCP server: RedFlag as tools for Claude Desktop (or any MCP client).

An analyst chatting with Claude can ask "what are Madhur Steel's covenants?" and Claude calls RedFlag, which answers
from the filing with a verified page citation, or declines. Claude can then open the cited page itself to check it.

Tools
  list_prospectuses()                    companies available
  ask_prospectus(doc, question)          verified, page-cited answer (or a decline)
  red_flag_memo(doc)                     the red-flag memo (cached; regenerated on request)
  read_page(doc, page)                   raw text of one page, so the caller can check a citation

Run (Claude Desktop config: see docs/claude_desktop.md)
    python -m redflag.mcp_server
"""

import sys
from pathlib import Path

if __package__ in (None, ""):  # started by file path (as Claude Desktop does): make the project importable
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from redflag.config import DOCS, REPORTS  # noqa: E402

mcp = MCPServer(
    name="redflag",
    instructions="Diligence answers from Indian IPO prospectuses (SEBI DRHPs). Every answer from ask_prospectus cites a "
                 "PDF page and has been checked against that page; if it returns found=false, do not guess the answer. "
                 "Use read_page to show the user the evidence.",
)


def _check_doc(doc: str) -> None:
    if doc not in DOCS:
        raise ValueError(f"unknown doc '{doc}'. Available: {', '.join(DOCS)}")


@mcp.tool()
def list_prospectuses() -> dict:
    """List the prospectuses RedFlag can answer questions about (id, company, sector, filing date)."""
    return {d: {k: v[k] for k in ("company", "sector", "filed", "basis")} for d, v in DOCS.items()}


@mcp.tool()
def ask_prospectus(doc: str, question: str) -> dict:
    """Answer a question from one prospectus. Returns the answer, value, unit, cited PDF page and verbatim quote.
    found=false means the answer is not in the document or could not be verified: report that instead of guessing."""
    _check_doc(doc)
    from redflag.qa import ask

    r = ask(question, doc)
    return {k: r.get(k) for k in ("found", "answer", "value", "unit", "page", "quote", "operation", "verified")}


@mcp.tool()
def red_flag_memo(doc: str, regenerate: bool = False) -> str:
    """Red-flag diligence memo for a prospectus, in Markdown, with page citations for every figure."""
    _check_doc(doc)
    path = REPORTS / f"memo_{doc}.md"
    if regenerate or not path.exists():
        from redflag.memo import run

        return run(doc)[1]
    return path.read_text(encoding="utf-8")


@mcp.tool()
def read_page(doc: str, page: int) -> str:
    """Raw text of one PDF page of a prospectus, to check a citation."""
    _check_doc(doc)
    from redflag.ingest import load_pages

    pages = load_pages(doc)
    if page not in pages:
        raise ValueError(f"page {page} does not exist (1-{max(pages)})")
    return pages[page]


if __name__ == "__main__":
    mcp.run("stdio")
