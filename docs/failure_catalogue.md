# Failure catalogue: how AI goes wrong on Indian financial documents, and what fixed it

Every entry was found while building RedFlag and CovenantWatch on three real DRHPs (1,552 pages), and each fix was
measured on the gold set where possible.

| # | Failure | How it showed up | Fix | Effect |
|---|---|---|---|---|
| F1 | **Unit mix-ups**: filings report in ₹ lakhs, ₹ million or ₹ crore, printed once above a table (often on the previous page) | Converting "revenue in ₹ crore": 0% correct without unit context (hybrid config) | Detect the unit per page, carry it to continuation pages, label every passage with it; do conversions in Python | Unit-conversion questions 0% (hybrid) → 67% (unit labels + compute) → 100% (final) |
| F2 | **Right-looking number, wrong line item** | "Revenue growth FY25→26" answered 30.62%, a figure the DRHP prints for **total income**; correct revenue growth is 30.76%. The citation check passed, because the quote really contains 30.62 | For growth / change / conversion questions the model must return the raw figures; Python computes. If it copies a percentage, verification sends it back | Growth questions are always computed from cited operands |
| F3 | **Printed vs PDF page numbers** | Covenant extraction cited "page 436" (the number printed on the page); the PDF page is 441. 26 of 38 covenants failed the citation check; recall 33% | If a quote is not on the cited page but exists on exactly one other page, cite that page (quote still verified); prompt says to use the page header | Madhur covenant recall 33% → 96%, 25 citations corrected |
| F4 | **"Hybrid search is best" was wrong here** | Recall@8: BM25 72%, MiniLM 86%, BM25+MiniLM 86%, **BGE-small 95%**, BM25+BGE 88% | Retriever chosen by measurement: dense BGE-small | Answer accuracy 78% (v1) → 89% (v2) together with F2 |
| F5 | **Model output shape** | `"operation": null`, numbers as `"18,628.02"` or `"(1,488.81)"` crashed validation | Tolerant validators (null → default, strings → numbers, brackets → negative) + one repair retry | No crashes in 46 × 5 runs |
| F6 | **My own bug: computed answer marked "not found"** | Two correct computed answers (−24.40%, ₹105.83 crore) scored wrong because a flag stayed false | Compute step sets found=true on success; caught by reading every wrong answer, not just the score | +2 questions |
| F7 | **Free-tier embedding quota** | Gemini embeddings: 1,000 requests/day; 5,359 passages would take 6 days | Local embedding models (MiniLM, BGE-small) on CPU; Gemini kept as an option for paid keys | Index built in ~20 min, no API cost, data never leaves the machine |
| F8 | **Loss sign** | "Loss of ₹67.09 million" returned as 67.09 or −67.09 | Scored sign-insensitively for "profit or loss" questions; memo rules read the sign from the statement | — |
| F9 | **Declining is a feature** | "FY2028 revenue forecast" (not in any DRHP) | Model may return found=false; unverifiable answers are declined after one retry | 3/3 declined in every configuration |
| F10 | **Classifier keyword traps** | Keyword rules flagged "a new distributor was **appointed**" as a management change; missed "block deal", "foreclosed", "recalled its facility" | LLM classifier with the taxonomy; keywords kept as the fallback when the API is down | Accuracy 67% → 92%, recall 61% → 89%, 0 false alerts on noise |
| F11 | **A popular fix that made things worse** | Test set grown to 94 questions; balance-sheet rows ("Total Assets 33,422.70") were often not retrieved | Tried contextual chunk headers (prefix each passage with its section and table title before embedding). **Recall@8 fell 88.6% → 80.7%**: every passage of a table got the same header and started to look alike | Reverted. Kept what the data supported: retrieve 12 passages instead of 8 (recall 88.6% → 92.0%) |
| F12 | **Laptop security policy blocked a library** | Windows Application Control started blocking gRPC's compiled module, which the vector-store client imports (local mode never uses it) | A stub is installed only when the import is blocked; no effect on Linux / the deployed app | Local runs work again; CI and cloud unaffected |
| F13 | **Free-tier limits differ per model and per axis** | Reconciliation stalled: Groq Qwen allows 8k input and **1k output tokens/minute** (one extraction needs ~1.1k out); Gemini 3.6 Flash allows **20 requests/day** | Context capped at 12 passages; long jobs moved to the model whose limits fit; limits recorded here | Long agent runs are planned against the provider's limits, not discovered mid-run |

## Things the documents got wrong (found while checking answers)

These are the findings a diligence team would want, and the AI did not flag them by itself:

1. **Madhur Iron & Steel: "secured" total includes unsecured loans.** The Financial Indebtedness summary (PDF p. 424)
   presents ₹26,945.94 lakh sanctioned / ₹25,249.31 lakh outstanding of fund-based facilities under "Secured".
   The detailed table (p. 438-440) splits the same totals into **Secured ₹16,125.38 lakh + Unsecured ₹9,123.93 lakh**
   (RXIL, Mizuho/KredX, Siemens, Tata Capital). About 36% of fund-based borrowing is labelled secured but is not.
2. **Anchor Offshore: tax cases 50 or 53?** The litigation summary in Risk Factors (p. 47) shows 50 tax proceedings
   against the Company; the Outstanding Litigation chapter (p. 375) lists 52 direct-tax + 1 indirect-tax cases.
3. **Numeric covenants not disclosed.** Atomberg's and Anchor's filings say financial covenants exist
   ("financial ratios beyond the prescribed limits") but give no numbers: a monitoring gap to close with the lenders.

**Lesson:** cross-section reconciliation (summary vs detailed tables) is a check worth building as its own agent step.
