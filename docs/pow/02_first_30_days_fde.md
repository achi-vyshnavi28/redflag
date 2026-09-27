# My first 30 days as a Forward Deployed Engineer at Binocs

*Written before joining, from public information about Binocs and what I learned building RedFlag and
CovenantWatch on real Indian filings. Anything about Binocs' internal product is an assumption to check in week 1.*

## The job as I understand it
Take Binocs' agent platform into a fund, make it produce investment-grade answers on **that fund's** documents and
workflows, measure it, fix what breaks, and bring what I learn back to Product and Engineering.

## A realistic first customer: a mid-size Indian PE / private-credit fund

### Week 1: learn the analyst's week, not just the documents
- Sit with 2 analysts and 1 partner. Map how a deal moves: screening → data room → model → IC memo → monitoring.
  Time each step. Note where they copy numbers by hand, reconcile tables, or chase management for answers.
- Collect 5 recent deals' documents (DRHPs / IMs / CIMs, financial statements, loan agreements, rating rationales)
  and the IC memos written from them. **The memos are the gold set: they show which facts the fund actually uses.**
- Agree on success metrics with the partner before building anything:
  | Metric | Why |
  |---|---|
  | Hours from data-room access to first-draft IC memo | the value the fund pays for |
  | % of memo claims with a correct page citation | investment-grade = checkable |
  | Unsupported-claim rate on a gold set | one wrong number destroys trust |
  | Analyst edits per memo section | proxy for usefulness |

### Week 2: build the fund's gold set and baseline
- Turn 50 facts from past IC memos into questions with known answers and pages (as I did for 46 questions in
  RedFlag). Include the hard types: numbers inside tables, figures that must be reconciled across sections,
  unit conversions (lakhs / million / crore), consolidated vs standalone, and questions whose answer is **not** in the documents.
- Run Binocs as-is on it. Read every wrong answer and sort it into a failure catalogue (see `docs/failure_catalogue.md`
  for the ten I hit: unit mix-ups, wrong line item, printed vs PDF page numbers, retrieval choice, quotas...).

### Week 3: fix the top failures and fit the workflow
- Fix the 2-3 failure types that cost the most; re-run the gold set after each fix and keep the before/after numbers.
- Connect where the analysts already work: data-room export, the fund's Excel model template, Slack / email for alerts.
- Set up monitoring for portfolio companies' covenants (CovenantWatch-style) if the fund does private credit:
  covenant register extracted from loan documents and **confirmed by an analyst** before going live.

### Week 4: prove it on a live deal
- Run a current deal end-to-end with the analysts. Measure hours saved and edits made; log every correction.
- Write the deployment report: what worked, what failed, what the customer asked for, and which of those should
  become product features vs stay as this customer's configuration.

## Risks I would manage from day one
| Risk | Control |
|---|---|
| Confidential deal data | Least-privilege access; embeddings can run locally (RedFlag uses on-CPU models); no customer data in prompts to vendors not approved by the fund |
| Wrong numbers reach an IC | Citations verified against the page; "not found" is allowed and preferred to a guess; human sign-off on the memo |
| Silent model changes | Pin model versions; re-run the gold set before switching models |
| Free-tier / rate limits in pilots | Caching, retries, local fallbacks (hit Gemini's 1,000-embeddings/day limit myself) |
| Adoption | Start where analysts lose the most time; ship small; weekly check-in with the partner |

## What I would bring back to Product
- The failure catalogue with counts per type, from real customer documents.
- The customer's requests, sorted into "product feature" vs "configuration" vs "not now".
- Reusable pieces: gold-set builder, citation verifier, unit normaliser, reconciliation checks.
