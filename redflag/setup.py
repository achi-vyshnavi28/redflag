"""First-run setup: download the public prospectuses from SEBI, extract pages, build chunks and the local index.

    python -m redflag.setup
"""

import os

import httpx

from redflag.config import DOCS, INDEX, PROCESSED, RAW


def download() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for doc, info in DOCS.items():
        path = RAW / f"{doc}.pdf"
        if not path.exists() and not (PROCESSED / f"{doc}_pages.json").exists():
            print(f"downloading {info['company']} DRHP from SEBI...", flush=True)
            r = httpx.get(info["url"], headers={"User-Agent": "Mozilla/5.0 (RedFlag research)"}, timeout=300, follow_redirects=True)
            r.raise_for_status()
            path.write_bytes(r.content)


def main() -> None:
    if os.getenv("REDFLAG_SKIP_SETUP"):
        return
    download()
    from redflag.ingest import build

    if not all((PROCESSED / f"{d}_chunks.jsonl").exists() for d in DOCS):
        print(build())
    if not (INDEX / "qdrant_minilm" / "collection" / "chunks_minilm").exists():
        from redflag.index import build_dense

        print("embedding chunks (MiniLM, local)...", build_dense("minilm"))


if __name__ == "__main__":
    main()
