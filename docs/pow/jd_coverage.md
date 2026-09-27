# Binocs – Forward Deployed Engineer: JD coverage

RF = RedFlag (this repo) · CW = [CovenantWatch](https://github.com/achi-vyshnavi28/covenantwatch) · RC = [RootCause](https://github.com/achi-vyshnavi28/rootcause)

## Listed skills
| Skill | Evidence |
|---|---|
| LLMs | RF, CW: Gemini models through one model-agnostic layer (LiteLLM), JSON outputs validated with pydantic, retries, caching, cost and latency logged |
| Agentic workflow / agentic AI | RF: LangGraph Q&A agent (retrieve → extract → compute → verify → retry or decline) and a multi-agent memo graph (4 section agents in parallel → rules → writer → guardrail). RC: LangGraph analyst agent |
| LangChain | RF: BM25 retriever and document model |
| Claude | RF, CW: `claude-sonnet` in the model registry, used when `ANTHROPIC_API_KEY` is set (not benchmarked: no key) |
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
| Prototypes into production | Dockerfiles, GitHub Actions CI that builds the image and calls the running API, pinned requirements, health checks, retries, graceful degradation |
| Customer feedback → product improvements | RF `/feedback` endpoint + log; CW analyst verdicts on every alert; RF `docs/pow/04_customer_feedback_guide.md` |
| Across engineering, AI, product, customer implementation | both repos include the build, the evaluation, and the deployment playbook |

## What we're looking for
| JD line | Evidence |
|---|---|
| Python fundamentals | both repos, 20 offline tests |
| APIs, databases, basic software engineering | FastAPI, SQLite with SQL views (`ROW_NUMBER`, `LAG`), Qdrant, tests, CI |
| Exposure to LLMs, GenAI, RAG, agents | above |
| Problem-solving and debugging | failure catalogue; two real inconsistencies found in the filings |
| Ambiguous problems → practical solutions | numeric covenants not disclosed → fund policy triggers until lenders share terms |
| Communication, working with customers | onboarding playbook, 30-day plan, memos written for an investment committee |

## Good to have
| Item | Evidence |
|---|---|
| OpenAI / Anthropic APIs, LangChain, LangGraph | LangChain + LangGraph used; OpenAI and Anthropic wired in, not benchmarked (no keys) |
| Building / deploying GenAI apps | RF and CW APIs + Streamlit apps + Docker; RC is deployed live |
| Git, Docker, cloud, SQL | Git, Docker, CI, SQL; cloud: RC on Streamlit Cloud |
| Fintech / financial research / investment workflows | IPO diligence (RF) and private-credit covenant monitoring (CW) on real Indian filings |

## Honest gaps
- Claude and OpenAI models are supported but not benchmarked (no API keys available to me).
- Docker is verified in CI, not on my laptop (virtualisation is disabled on it).
