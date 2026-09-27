# Where the facts for an Indian deal live, and which connectors to build first

*From public sources and my own work on SEBI filings. Access terms and costs change, so verify before building.*

| Source | What a diligence team gets from it | Format / access | Effort to connect | Priority |
|---|---|---|---|---|
| **SEBI offer documents** (DRHP / RHP) | 3 years of restated financials, borrowings and covenants, litigation, related parties, promoters, risk factors | Public PDFs on sebi.gov.in (400-600 pages) | Low. RedFlag downloads, parses and indexes them | **1** |
| **Credit rating rationales** (CRISIL, ICRA, CARE, India Ratings) | Leverage, liquidity, outlook changes, rating history; early warning for credit | Public HTML/PDF per company | Low-medium (per-agency formats) | **2** |
| **Stock exchange filings** (BSE / NSE corporate announcements) | Quarterly results, board decisions, pledges, KMP changes, events that trigger covenants | Public announcements; PDFs + structured feeds | Medium (volume, dedupe) | **3** |
| **MCA21 company filings** (annual returns, financial statements, charges) | Private companies' financials, **charges registered** (who has lent against what), directors | Paid per-document downloads from the MCA portal | Medium-high (paid, scanned PDFs, OCR) | 4 |
| **Court and tribunal records** (eCourts, NCLT) | Litigation and insolvency petitions not yet in filings | Public search, inconsistent formats | High (entity matching) | 5 |
| **Customer's own data room** | CIMs, management accounts, loan agreements, compliance certificates | Customer-provided (VDR export) | Depends on customer | Always, first per customer |
| **Commercial databases** (e.g. corporate data aggregators) | Pre-cleaned financials for private companies | Paid API / exports | Low once licensed | Customer's choice |

## Why this order
1. **DRHPs first**: highest information density per document, fully public, and exactly where the hard problems are
   (tables, units, cross-section reconciliation). Everything built here transfers to CIMs.
2. **Rating rationales second**: short, frequent, and they move before defaults do. For private credit they are the
   cheapest early-warning signal (CovenantWatch treats a downgrade as a possible event of default).
3. **Exchange announcements third**: they are the event stream for covenant monitoring (dividends, pledges,
   KMP changes, fresh borrowing), which CovenantWatch's classifier maps to covenant topics.

## Data traps specific to Indian documents
- Units: ₹ lakhs vs ₹ million vs ₹ crore, often printed once per table (1 crore = 100 lakhs = 10 million).
- Lakh-style digit grouping: 1,10,00,000 = 11,000,000.
- Standalone vs consolidated statements side by side.
- Fiscal year labels: "Fiscal 2026" = year ended 31 March 2026.
- Printed page numbers differ from PDF page numbers (cost me 26 failed citations until fixed).
- Summary tables that do not match the detailed tables (found two such cases in three DRHPs).
