"""Turn a prospectus PDF into searchable chunks that remember their page, section and reporting unit.

Two details matter for investment-grade answers:
  * page:    every chunk keeps its PDF page, so every answer can cite it
  * unit:    Indian filings mix "₹ in lakhs", "₹ in million" and "₹ in crore". The unit is usually printed once
             above a table, often on the previous page. It is detected per page and carried into each chunk,
             so the model never has to guess (see docs/failure_catalogue.md, F1)
  * section: the chapter a page belongs to (e.g. FINANCIAL INDEBTEDNESS), used for filtering and for the memo

    python -m redflag.ingest
"""

import json
import re

import pypdf
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter

from redflag.config import DOCS, PROCESSED, RAW

UNIT = re.compile(r"(?:₹|Rs\.?|INR)\s*(?:in\s+)?(lakhs?|lacs?|million|crores?|billion)\b", re.I)
UNIT_NAMES = {"lakh": "lakhs", "lakhs": "lakhs", "lac": "lakhs", "lacs": "lakhs", "million": "million",
              "crore": "crore", "crores": "crore", "billion": "billion"}
SECTIONS = ["SUMMARY OF THE OFFER DOCUMENT", "SUMMARY OF THE ISSUE DOCUMENT", "RISK FACTORS", "SUMMARY FINANCIAL INFORMATION",
            "SUMMARY OF FINANCIAL INFORMATION", "CAPITAL STRUCTURE", "OBJECTS OF THE", "BASIS FOR", "INDUSTRY OVERVIEW",
            "OUR BUSINESS", "KEY REGULATIONS", "HISTORY AND CERTAIN CORPORATE", "OUR MANAGEMENT", "OUR PROMOTER",
            "OUR GROUP COMPAN", "DIVIDEND POLICY", "RESTATED", "OTHER FINANCIAL INFORMATION", "CAPITALISATION STATEMENT",
            "MANAGEMENT'S DISCUSSION", "MANAGEMENT’S DISCUSSION", "FINANCIAL INDEBTEDNESS", "OUTSTANDING LITIGATION",
            "GOVERNMENT AND OTHER APPROVALS", "OTHER REGULATORY AND STATUTORY", "MAIN PROVISIONS OF ARTICLES", "DECLARATION"]


def extract_pages(doc: str) -> list[dict]:
    cache = PROCESSED / f"{doc}_pages.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    reader = pypdf.PdfReader(RAW / f"{doc}.pdf")
    pages = [{"doc": doc, "page": i + 1, "text": p.extract_text() or ""} for i, p in enumerate(reader.pages)]
    PROCESSED.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(pages), encoding="utf-8")
    return pages


def page_units(pages: list[dict], carry: int = 2) -> list[str | None]:
    """Unit printed on each page; a table continuing onto the next page(s) inherits the last unit seen."""
    out, last, since = [], None, 99
    for p in pages:
        found = UNIT.findall(p["text"][:1500])
        if found:
            last, since = UNIT_NAMES[found[0].lower()], 0
        else:
            since += 1
        out.append(last if since <= carry else None)
    return out


def page_sections(pages: list[dict]) -> list[str]:
    out, current = [], "FRONT MATTER"
    for p in pages:
        head = "\n".join(p["text"].splitlines()[:6]).upper()
        for s in SECTIONS:
            if re.search(r"^\s*" + re.escape(s), head, re.M):
                current = s.replace("’", "'").rstrip()
                break
        out.append(current)
    return out


def chunk(doc: str, chunk_size: int = 350, overlap: int = 60) -> list[dict]:
    pages = extract_pages(doc)
    units, sections = page_units(pages), page_sections(pages)
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    documents = [Document(text=re.sub(r"[ \t]+", " ", p["text"]), metadata={"doc": doc, "page": p["page"], "unit": u, "section": s},
                          excluded_embed_metadata_keys=["doc", "page", "unit", "section"])
                 for p, u, s in zip(pages, units, sections) if p["text"].strip()]
    nodes = splitter.get_nodes_from_documents(documents)
    return [{"id": f"{doc}-{i}", "text": n.get_content(), **n.metadata} for i, n in enumerate(nodes)]


def build() -> dict:
    counts = {}
    for doc in DOCS:
        chunks = chunk(doc)
        (PROCESSED / f"{doc}_chunks.jsonl").write_text("\n".join(json.dumps(c) for c in chunks), encoding="utf-8")
        counts[doc] = len(chunks)
    return counts


def load_chunks(doc: str | None = None) -> list[dict]:
    docs = [doc] if doc else list(DOCS)
    out = []
    for d in docs:
        out += [json.loads(line) for line in (PROCESSED / f"{d}_chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    return out


def load_pages(doc: str) -> dict[int, str]:
    return {p["page"]: p["text"] for p in extract_pages(doc)}


if __name__ == "__main__":
    print(build())
