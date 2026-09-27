# Reviewing the AI's red-flag memos like an analyst would

RedFlag wrote a first-pass diligence memo for each of three real DRHPs ([Madhur Steel](../../reports/memo_madhur_steel.md),
[Atomberg](../../reports/memo_atomberg.md), [Anchor Offshore](../../reports/memo_anchor_offshore.md)): 21 checklist
questions each, about $0.008 of model cost per memo, every figure with a page citation that passed an automatic check.

Then I read each memo against the filing, the way an analyst would before it goes to an investment committee.

## What the AI got right (and is worth a question to management)

| Company | Red flag | Evidence |
|---|---|---|
| Anchor Offshore | **Trade receivables up 71.8% while revenue fell 24.4%** (₹399.96M → ₹687.19M vs ₹1,399.89M → ₹1,058.27M) | restated balance sheet and P&L |
| Atomberg | **Restated loss of ₹148.88 crore** in FY2026; EBIT does not cover finance costs (interest cover −2.32x) | restated P&L, p. 83 |
| Atomberg | **Claims against the company of ₹377.68 crore = 203% of total equity**; one material civil case against the promoters | litigation summary, p. 50 |
| Madhur Steel | Borrowings ≈ 1.6x equity; finance costs of ₹1,847 lakh against PBT of ₹3,239 lakh | restated statements |

## What the AI got wrong: the citation was real, the meaning was not

Automatic checks confirm that the quoted number **is on the cited page**. They cannot tell whether it is the **right
number**. All three errors below passed the citation check.

1. **Three definitions of "borrowings" in one ratio (Madhur Steel, v1 memo).**
   - Current borrowings ₹18,277.99 lakh came from the MD&A contractual-obligations table (p. 478): *short-term
     borrowings excluding* the ₹350.03 lakh of term loans due within a year.
   - Non-current borrowings ₹909.09 lakh came from the company's non-GAAP debt-equity reconciliation (p. 416), which
     *includes lease liabilities* (864.53 + 44.56).
   - The restated balance sheet (p. 85, p. 84) says ₹18,628.02 and ₹864.53 lakh.
   The ratio moved only from 1.65x to 1.63x, but a memo that mixes definitions cannot be defended at an IC.
   **Fix:** balance-sheet and P&L questions now ask for the restated statement figure explicitly.
2. **"By" read as "against" (Anchor Offshore).** A management question cites "litigation against the company amounting
   to ₹49.71 million". On p. 47 that amount is litigation filed **by** the company; claims **against** it total ₹0.92 million.
   **Fix to build:** extract litigation tables as structured rows (party, direction, count, amount) instead of free text.
3. **Growth for the wrong line item (evaluation).** Asked for revenue growth, the model quoted 30.62%, which the DRHP
   prints for **total income**; revenue grew 30.76%. **Fixed:** growth is always computed in Python from cited raw figures.

## What neither the AI nor its checks found, but the documents contain

- **Madhur Steel: ₹91 crore of unsecured loans labelled "secured".** The indebtedness summary (p. 424) lists all
  ₹25,249.31 lakh of fund-based borrowing under "Secured"; the detailed table (p. 438-440) shows ₹9,123.93 lakh of it
  is unsecured (RXIL, Mizuho/KredX, Siemens, Tata Capital).
- **Anchor Offshore: 50 or 53 tax cases?** Risk-factor summary (p. 47): 50. Litigation chapter (p. 375): 52 + 1.

Both are **reconciliation** problems: two parts of one filing that should agree and don't. A single-question RAG
system will never notice them, because each part is internally consistent.

## What I would build next (in order)
1. **Reconciliation agent**: for each key figure (borrowings, litigation counts, revenue), find every place it appears,
   group by definition, and flag disagreements. It would have found all four issues above.
2. **Structured table extraction** for litigation and indebtedness tables (party, direction, amount, secured/unsecured).
3. **Definition-aware questions**: every financial fact stored with its source statement (restated / MD&A / non-GAAP).

*Scope: three memos, reviewed by me. Not investment advice.*
