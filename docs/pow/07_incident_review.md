# Incident review: CovenantWatch API hung in production when no LLM key was configured

**Audience:** Engineering. **Format:** blameless post-incident review.
**Status:** resolved. **Author:** Vyshnavi Achi. **Date:** 27 Sep 2026

*This happened while shipping CovenantWatch; the write-up is how I would report it to an engineering team.*

## Summary
After deployment, the CovenantWatch container started and passed its health check, but the first call to run the
daily monitor (`POST /run`) never returned. The CI job that exercises the running container stayed "in progress" for
over 25 minutes until I investigated. No alerts were produced, so in a real deployment **covenant breaches would have
gone unreported with no error visible to anyone**.

## Impact
- Monitoring silently stopped for any environment without an LLM API key (CI, a new customer before keys are issued,
  or a revoked key).
- The health check still reported the service as healthy, so nothing would have paged anyone.

## Timeline
| Time | Event |
|---|---|
| T0 | Pushed a fix for a different start-up bug; CI rerun started |
| T0 + 3 min | Tests pass; Docker image builds; container healthy |
| T0 + 25 min | CI step "API starts, runs the monitor and serves alerts" still running; flagged as abnormal |
| T0 + 28 min | Read the job steps through the GitHub API: stuck on the `/run` call, not on build or start-up |
| T0 + 32 min | Reproduced locally with the key unset: classifying one event did not return within 90 s |
| T0 + 40 min | Fix pushed; locally the same call now falls back to keyword triage in under 5 s |
| T0 + 55 min | CI green on both repositories |

## Root cause
Event triage calls an LLM and, by design, falls back to keyword rules if the model fails. The fallback only triggered
on an **error**. With no API key configured, the call did not error quickly: locally it produced nothing for 90 seconds
before I stopped it. I did not trace exactly where inside the model client it waited, and our retry wrapper (built to
ride out rate limits) could only make such a wait longer. The code assumed "no key" would look like "fast failure";
it looked like "slow network". The fix does not depend on where the wait happens: it never makes the call without a key.

## Why it wasn't caught earlier
- Unit tests replace the classifier with a fake, so they never exercised the real client without a key.
- The health endpoint checks that the web server responds, not that a monitoring run completes.
- The CI job had no time limit, so a hang looked like a slow run instead of a failure.

## Fixes
| Fix | Where | Status |
|---|---|---|
| Check for the provider's key **before** calling the model; raise immediately so the fallback runs | `llm.py` (both repos) | Done |
| 15-minute limit on the Docker CI job; 5-minute limit on the `/run` call | `.github/workflows/ci.yml` | Done |
| Test that runs the monitor with no key and asserts it completes quickly | test suite | Proposed |
| Health endpoint reports time since the last successful monitoring run | `api.py` | Proposed |
| Alert if no monitoring run has completed in 26 hours ("dead man's switch") | scheduler | Proposed |

## Lessons
1. **A fallback that depends on an error is only as good as the error.** Check preconditions explicitly.
2. **"Healthy" should mean "doing its job"**, not "responding to pings", for anything that must run every day.
3. **Every automated job needs a time limit.** A hang is worse than a crash because nobody notices it.
