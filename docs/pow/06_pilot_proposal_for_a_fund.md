# Pilot proposal: AI-assisted IPO and credit diligence

**To:** Partner, [Mid-size Indian PE / private credit fund]
**From:** Vyshnavi Achi, Forward Deployed Engineer
**Re:** A 4-week pilot on your next two deals

*A sample of how I would write to a customer. The fund is hypothetical; every number about the software is real and
comes from the evaluation in this repository.*

---

## The short version

Your analysts spend the first days of every deal reading 400-600 page documents to find a few dozen facts and the
problems hidden in them. I'd like to run a 4-week pilot where our system produces a first-draft red-flag memo on your
next two deals, **with every figure linked to its page**, and we measure how many analyst hours it saves and how many
corrections your team has to make.

## What it does today, measured

We tested it on three real prospectuses filed with SEBI in August-September 2026 (1,552 pages), using 46 questions whose
answers we checked by hand.

| What we measured | Result |
|---|---|
| Questions answered correctly | **89%** (up from 65% for a standard AI search setup) |
| Answers where the cited page really contains the figure | 95-100%, depending on the model |
| Questions whose answer is not in the document | declined all 3 rather than guessing |
| Time and cost per answer | about 2 seconds, under ₹0.10 |

It also flagged things your team would want to ask about: at one company, **receivables up 72% while revenue fell 24%**;
at another, **claims against the company equal to twice its equity**.

## What it does not do, and how we handle that

I would rather you hear this from me than discover it on a live deal.

- **A correct citation is not always the right number.** In testing, the system once quoted a growth rate for total
  income when asked about revenue, and once mixed three different definitions of "borrowings". Both passed the
  automatic page check. We fixed both patterns, but **an analyst still reviews every memo before it goes to IC.**
- **It does not reconcile one part of a document against another.** Two filings we tested contained internal
  inconsistencies (one labels about ₹91 crore of unsecured loans as secured). A person found those, not the system.
  Building that check is on our roadmap, and your deals would help us test it.
- **It works from the documents you give it.** It does not know market context or management quality.

## The pilot

| Week | What happens | What you give | What you get |
|---|---|---|---|
| 1 | We sit with two analysts for a day; you share 3 past deals with their IC memos | 2 analyst-days, past documents | A test set built from **your** IC memos, and our baseline accuracy on it |
| 2 | We fix the top failure types on your documents | 1 hour of analyst review | Before / after accuracy on your test set |
| 3-4 | Live use on your next two deals | Analysts use it alongside their normal process | First-draft memos with page citations; hours and corrections logged |

**Success, agreed upfront:** first-draft memo in under a day from data-room access; at least 90% of memo figures correct
on your test set; your analysts say they would keep using it.

**Confidentiality:** documents stay within the environment we agree on. The search index can run entirely on your own
machines (it does not need to send documents to an external service to be searched).

## What I need from you

1. A 30-minute call this week to choose the two deals.
2. Two analysts for one day in week 1.
3. Honest feedback: every correction your team makes is how the system gets better.

Vyshnavi
