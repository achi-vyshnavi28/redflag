# Binocs – Forward Deployed Engineer: JD coverage

RF = RedFlag (this repo) · CW = [CovenantWatch](https://github.com/achi-vyshnavi28/covenantwatch) · RC = [RootCause](https://github.com/achi-vyshnavi28/rootcause)

## Listed skills
| Skill | Evidence |
|---|---|
| LLMs | RF, CW: Gemini models through one model-agnostic layer (LiteLLM), JSON outputs validated with pydantic, retries, caching, cost and latency logged |
| Agentic workflow / agentic AI | RF: LangGraph Q&A agent (retrieve → extract → compute → verify → retry or decline) and a multi-agent memo graph (4 section agents in parallel → rules → writer → guardrail). RC: LangGraph analyst agent |
| LangChain | RF: BM25 retriever and document model |
| Claude / OpenAI | RF: **MCP server** so Claude (Desktop) can call RedFlag's tools ([setup](../claude_desktop.md)); OpenAI gpt-oss-120b benchmarked (87.0%) alongside Gemini (89.1%) and Qwen (89.1%, 100% citations); CW: all three 92% on event triage. Claude API integrated, not benchmarked (no key) |
| LlamaIndex | RF: page documents and sentence-aware chunking with page / unit / section metadata |
| RAG | RF: page-cited answers over 1,552 pages; 5 retrievers compared (recall@8: BM25 72%, MiniLM 86%, hybrid 86-88%, **BGE 95%**) |
| Embedding models | RF: MiniLM vs BGE-small (local), Gemini embeddings supported; chosen by measurement |
| Vector databases | RF: Qdrant (one local store per embedder) |

## What you'll do
| JD line | Evidence |
|---|---|
| Understand customer workflows and requirements | CW `docs/onboarding.md`; RF `docs/pow/02_first_30_days_fde.md`; analyst confirmation step before monitoring |
| Build and customise AI/LLM solutions for real use cases | RF on real SEBI DRHPs; CW on real covenants from three borrowers |
| Prototypes, integrations, APIs, automation workflows | RF and CW FastAPI services; CW daily job, Slack notifications, idempotent alerts |
| LLMs, RAG, AI agents, frameworks | above |
| Debug and improve performance and reliability | RF `docs/failure_catalogue.md`: 10 failures, each with fix and measured effect (accuracy 65% → 89%); CW page-citation fix (recall 33% → 96%) |
| Prototypes into production | Deployed apps; Dockerfiles; GitHub Actions CI that builds the image and calls the running API; a quality gate that fails the build if retrieval recall or answer accuracy regresses; health checks, retries, graceful degradation |
| Customer feedback → product improvements | RF `/feedback` endpoint + log; CW analyst verdicts on every alert; feedback sorted into build / configure / not-now (08); interview guide (04) |
| Across engineering, AI, product, customer implementation | both repos include the build, the evaluation, and the deployment playbook |

## What we're looking for
| JD line | Evidence |
|---|---|
| Python fundamentals | both repos, 20 offline tests |
| APIs, databases, basic software engineering | FastAPI, SQLite with SQL views (`ROW_NUMBER`, `LAG`), Qdrant, tests, CI |
| Exposure to LLMs, GenAI, RAG, agents | above |
| Problem-solving and debugging | failure catalogue; two real inconsistencies found in the filings |
| Ambiguous problems → practical solutions | numeric covenants not disclosed → fund policy triggers until lenders share terms |
| Communication, working with customers | Written for three audiences: a pilot proposal for a fund partner (06), an incident review for engineers (07), a customer update + product-feedback note (08); plus the onboarding playbook, 30-day plan and IC-style memos |

## Good to have
| Item | Evidence |
|---|---|
| OpenAI / Anthropic APIs, LangChain, LangGraph | LangChain + LangGraph used; OpenAI gpt-oss benchmarked via Groq; Anthropic wired in, not benchmarked (no key) |
| Building / deploying GenAI apps | **Live:** [RedFlag](https://redflag1.streamlit.app), [CovenantWatch](https://covenant-monitor.streamlit.app), RootCause; APIs in Docker with CI |
| Git, Docker, cloud, SQL | Git, Docker, CI with a quality gate, SQL; cloud: all three apps on Streamlit Community Cloud with platform-managed secrets |
| Fintech / financial research / investment workflows | IPO diligence (RF) and private-credit covenant monitoring (CW) on real Indian filings |

## Honest gaps
- Claude is supported but not benchmarked (no API key); OpenAI is covered by its open-weight gpt-oss-120b via Groq.
- Docker is verified in CI, not on my laptop (virtualisation is disabled on it).
