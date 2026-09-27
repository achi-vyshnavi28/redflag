# Loom script (4 minutes)

**Tabs, in order:** RedFlag app (Ask tab) → a red-flag memo → failure catalogue → CovenantWatch dashboard.

**0:00-0:25 Hook**
"Hi, I'm Vyshnavi. Binocs helps funds do diligence in hours instead of weeks, so I tried a small version of that on
three real IPO prospectuses filed with SEBI last month: 1,552 pages. Every answer cites its page, and I measured
how often it's right."

**0:25-1:30 RedFlag, ask a question**
- Ask "What were current borrowings as at March 31, 2026?" for Madhur Steel. Open the cited page and show the highlighted quote.
- Ask the FY2028 forecast question. "It declines, because the answer isn't in the document. For a fund, a refusal beats a guess."
- "On 46 questions with known answers, plain RAG got 65% right. After four fixes it gets 89%, and it declined every question whose answer wasn't there."

**1:30-2:30 What broke and what I did**
- Failure catalogue: "Units: filings mix lakhs, million and crore, printed once above a table. I label every passage with its unit and do the maths in Python."
- "The scariest one: asked for revenue growth, it quoted 30.62%, the figure printed for total income. The citation was real, the number was wrong. Now growth is always computed from the raw figures."
- "And I assumed hybrid search would win. I measured five retrievers; plain BGE embeddings found the evidence 95% of the time vs 88% for hybrid, so I switched."

**2:30-3:15 The memo, and what I caught that the AI didn't**
- Anchor Offshore memo: "receivables up 72% while revenue fell 24%: that's a real question for management."
- "Reviewing it, I caught two things the AI didn't: it mixed three different 'borrowings' definitions, and it called litigation *by* the company litigation *against* it. And in the filings themselves I found a summary table labelling ₹91 crore of unsecured loans as secured."

**3:15-3:55 CovenantWatch**
- Dashboard: "For private credit I built a covenant monitor. It pulled the real covenants from the loan sections, like debt-to-equity 3.33:1, and I replayed a simulated year: it caught all 15 planted problems, including a stock statement late for one lender but not another."

**3:55-4:10 Close**
"What I'd do in my first month as a forward deployed engineer is in the repo: build the customer's gold set from their own IC memos, measure, fix the top failures, and ship it on a live deal. Links below."
