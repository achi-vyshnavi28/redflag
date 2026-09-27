# End of week 2: customer update, and what I'm taking back to Product

*Two short pieces written for a hypothetical pilot at a private-credit fund. The system behaviour described is real
(from testing RedFlag and CovenantWatch); the customer and their reactions are illustrative.*

---

## 1. Email to the customer

**Subject:** Pilot week 2: what we found, what we fixed, what's next

Hi Priya,

A quick update after two weeks.

**What's working**
- Covenant registers for your three borrowers are extracted and were confirmed by Rahul on Tuesday. Every covenant
  links to its page in the loan document; the three financial limits (debt-to-equity 3.33x, security cover 1.33x,
  asset cover 0.3x) were exactly right.
- The daily check is running. This week it flagged one borrower's stock statement as late for Bajaj Finance
  (due the 20th) but on time for RBL Bank (due the 25th). Rahul confirmed that's correct: the two lenders have different deadlines.

**What we fixed after your team's feedback**
- Your analysts said alerts about "management changes" were too noisy (a new distributor appointment was being flagged).
  We switched that check from keyword rules to the AI classifier; on our test set, false alerts on routine news went
  from 1 to 0 and real issues caught rose from 61% to 89%.
- Monitoring briefly stopped on Monday because of a configuration issue on our side. It is fixed, and we added an alert
  so that if the daily check ever stops running, we hear about it within a day. Nothing was missed: I re-ran the
  checks for the affected days.

**Where I need your help**
- Two borrowers' filings mention financial covenants but don't state the limits. Could someone share their sanction
  letters? Until then, we're watching them against your fund's own thresholds.

**Next week:** backfill the last eight quarters so we can compare our alerts with what your team already knew.

Thanks,
Vyshnavi

---

## 2. Note to Product and Engineering

**From the pilot, week 2. Sorted into: build into the product / configure per customer / not now.**

| # | What the customer said or did | What it means | Recommendation |
|---|---|---|---|
| 1 | "Which borrowings figure is this?" (analyst, looking at a leverage ratio) | Filings print several definitions of the same line item; users need to see which one we used | **Build:** store and show the source statement (restated / MD&A / non-GAAP) with every figure |
| 2 | Analyst checked two sections of a filing against each other by hand and found a mismatch | Reconciliation is manual today and high value; single-question AI can't catch it | **Build:** reconciliation check across sections for key figures (borrowings, litigation, revenue) |
| 3 | "Can the digest come at 9 am, grouped by borrower?" | Timing and grouping preferences | **Configure** per customer |
| 4 | Two lenders, same covenant, different deadlines | Covenants must be stored per lender, not per borrower | **Build** (already how CovenantWatch works; keep it in the core product) |
| 5 | "Can it read our Excel models too?" | Real need, but a separate integration | **Not now:** revisit after the pilot, with two more customers asking |

**Metrics to watch:** analyst verdicts on alerts (false-positive rate), corrections per memo, hours from data room to first draft.
