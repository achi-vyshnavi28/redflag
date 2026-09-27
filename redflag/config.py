"""Paths, documents and model registry."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
INDEX = ROOT / "data" / "index"
CACHE = ROOT / ".cache"
REPORTS = ROOT / "reports"

for env in (ROOT / ".env", ROOT.parents[1] / "rootcause" / ".env"):
    if env.exists():
        load_dotenv(env)

# Public Draft Red Herring Prospectuses (DRHPs) filed with SEBI.
DOCS = {
    "atomberg": {
        "company": "Atomberg Technologies Limited",
        "sector": "Consumer electrical appliances (fans, BLDC motors)",
        "filed": "2026-08-20",
        "basis": "consolidated",
        "url": "https://www.sebi.gov.in/sebi_data/attachdocs/aug-2026/1787809930622.pdf",
    },
    "madhur_steel": {
        "company": "Madhur Iron & Steel (India) Limited",
        "sector": "Steel products trading and manufacturing",
        "filed": "2026-09-14",
        "basis": "standalone",
        "url": "https://www.sebi.gov.in/sebi_data/attachdocs/sep-2026/1789720399852.pdf",
    },
    "anchor_offshore": {
        "company": "Anchor Offshore Services Limited",
        "sector": "Marine and offshore engineering services",
        "filed": "2026-09-15",
        "basis": "consolidated",
        "url": "https://www.sebi.gov.in/sebi_data/attachdocs/sep-2026/1789731006415_1354.pdf",
    },
}

# Any LiteLLM model id works; these are the ones evaluated. Prices are list prices per 1M tokens (USD) used to
# estimate cost per answer; the free tier was used for the runs themselves.
MODELS = {
    "gemini-3.5-flash-lite": {"id": "gemini/gemini-3.5-flash-lite", "in": 0.10, "out": 0.40},
    "gemini-3.8-flash": {"id": "gemini/gemini-3.8-flash", "in": 0.30, "out": 2.50},
    "gemini-3.6-flash": {"id": "gemini/gemini-3.6-flash", "in": 0.30, "out": 2.50},
    "gemma-4-31b": {"id": "gemini/gemma-4-31b-it", "in": 0.0, "out": 0.0},  # open weights: self-hostable
    "claude-sonnet": {"id": "anthropic/claude-sonnet-4-5", "in": 3.00, "out": 15.00},  # used when ANTHROPIC_API_KEY is set
    "gpt": {"id": "openai/gpt-5-mini", "in": 0.25, "out": 2.00},  # used when OPENAI_API_KEY is set
}
DEFAULT_MODEL = os.getenv("REDFLAG_MODEL", "gemini-3.5-flash-lite")
EMBEDDERS = {
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",  # local, 384 dims, runs on CPU via ONNX (fastembed)
    "bge": "BAAI/bge-small-en-v1.5",  # local, 384 dims, stronger on retrieval benchmarks than MiniLM
    "gemini": "gemini/gemini-embedding-001",  # API; free tier allows 1,000 embeddings/day, so not used for the full index
}
