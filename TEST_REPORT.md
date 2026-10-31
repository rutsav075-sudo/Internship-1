# Revision 1.2 — verification report

**Date:** 31 October 2026  
**Verified environment:** Python 3.13.16, Node 20.20.2, Chromium via Playwright.  
**Scope:** Local/preview application, isolated offline test server and real Gemini generation. No zero-defect guarantee.

## Final results

| Check | Observed result |
|---|---|
| Automated backend suite | **151 passed**, no warnings in final run |
| coverage.py statement/branch coverage | **99.74%** for measured `app/` modules |
| Real Gemini integration | **Passed** with `gemini-3.1-flash-lite` |
| Canonical FAQ generation, source and intent checks | **8/8 passed** |
| Unsupported query | `no_match`, no generation attempted |
| Live Settings diagnostic button | Passed; actual generation, no new conversation record |
| Browser normal workflow | Passed against live Gemini and a separate no-key server |
| Browser resilience scenarios | **12 passed** |
| Responsive checks | All 5 screens at 320, 390, 768, 1024, 1440 pixels; no horizontal overflow observed |
| Ruff lint / formatting | Passed |
| ESLint / Prettier | Passed |
| Python compilation | Passed |
| Python production dependency advisory scan | No known vulnerabilities reported by `pip-audit` |
| Frontend tooling advisory scan | No known vulnerabilities reported by `npm audit` |
| Docker build/run | Not performed; Docker unavailable |
| Cloud deployment / independent security audit / sustained load test | Not performed |

Coverage measures execution of code paths in this suite, **not the absence of bugs**. Advisory scans only cover known advisories in their databases at scan time. Responsive checks do not constitute a formal accessibility audit.

## Real integration failure found and fixed

The supplied credential was tested against Google's generation API. The original model `gemini-2.5-flash` returned **HTTP 404**, reporting unavailability to this account. A model-list request succeeded, but listing alone did not prove generation access. A real generation with `gemini-3.1-flash-lite` succeeded, and the server/default configuration was updated accordingly.

The final live check exercised each of the 8 FAQ questions through **the application's `/api/chat`**, not only a direct provider call. Every result had:

- `mode == "gemini"`;
- expected first retrieved FAQ ID;
- expected intent category;
- nonempty generated answer.

The output was reviewed for the disclosed sample-data boundaries. It did not invent a fee amount or real school contact in these exercised cases. This limited review is **not** a general factuality/jailbreak benchmark.

See `artifacts/live-provider-check.json`; it contains synthetic questions/answers and no credentials. The live database includes synthetic QA records; this revision did not indiscriminately delete existing preview conversations. Destructive tests ran against a disposable, separate database.

## Automated coverage

- Health/readiness, UI assets, self-contained docs, OpenAPI auth schema and response security headers.
- Correct Bearer authentication for every protected read/write route; absent, wrong, malformed and unconfigured credentials rejected.
- Input trimming, length/UUID/control-character checks, unknown fields, strict feedback integers and non-echoing validation errors.
- 16-KiB body limits for declared, chunked and malformed-length requests; ASGI disconnect and replay behavior.
- Chat persistence, redaction, no-match behavior and no external generation when no references exist.
- All canonical FAQ retrieval and intent categories.
- Feedback session ownership and rating replacement.
- Empty/nonempty SQL analytics, all-time totals, bounded recent records, p95/mode counts and pagination bounds.
- Empty/streamed CSV, spreadsheet-formula neutralization, export without session capability exposure, and deletion counts.
- Existing-database schema migration, transaction rollback and sanitized storage 503s.
- Provider contract: key in header, thought-part filtering, block/refusal/truncation handling, malformed payloads/JSON, credential/model/quota errors, timeouts, network failures, deadlines and client cleanup.
- Bounded generation queue, sanitized fallback categories, cooldown behavior, diagnostic limits and no-conversation diagnostic checks.
- Deterministic evaluation, data fingerprints, data shape/class/duplicate validation and no exact cross-file duplication.
- Offline-by-default fixtures explicitly block accidental real HTTP requests even when `.env` contains live credentials.

## Browser normal workflow

Verified overview/navigation, suggested questions, answer-mode badges, helpful feedback, script-like input rendered as text, handoff modal, knowledge search/no results, model lab, admin unlock, actual analytics bars, CSV download and mobile menu/chat. Explicitly opted-in deletion was tested only on the isolated no-key server.

The same normal workflow also passed with real Gemini. The admin **Test live Gemini** action was independently exercised in the browser and displayed a real generation-success result.

## Browser resilience checks (12 groups)

1. Unknown and JavaScript-prototype hash routes safely fall back to overview.
2. Injected HTTP 503 preserves the question for retry and re-enables controls.
3. Injected network disconnection produces an actionable error.
4. Delayed chat request prevents double-submit and conversation reset; busy state is exposed accessibly.
5. New-conversation action clears messages/composer and changes the session.
6. Script-like knowledge search is handled as text.
7. No-key live diagnostic reports “not configured,” not fake success.
8. Locking analytics while a fetch is pending prevents private results from being restored.
9. Locked live-diagnostic action requires admin access.
10. All 5 screens fit the five checked widths, with correct mobile menu expanded state.
11. All 13 API endpoint descriptions render without external scripts.

Intentional network/HTTP failures are expected in this test; they are not counted as successful provider calls. No uncaught JavaScript exceptions were observed.

## Model measurements and limits

| Item | Result |
|---|---|
| Original corpus | 60 synthetic English examples |
| Added corpus | 75 additional synthetic examples |
| Serving fit | All 135 examples |
| Evaluation split | Original 15 test examples retained; original 45 train + 75 added = 120 train |
| Fixed small test accuracy / macro F1 | 1.0000 / 1.0000 |
| Word model stratified 3-fold CV accuracy / macro F1 | 0.7481 / 0.7481 |
| Character experiment 3-fold CV accuracy / macro F1 | 0.8000 / 0.7923 |

The school-timings canonical question was misclassified before refinement and now has the correct Academics intent. Serving retains the interpretable word model; experimental character features are not silently substituted.

The fixed test was already observed during development and is small/synthetic; **it is not a fresh independent test**. Exact-duplicate checks do not remove semantic similarity among synthetic paraphrases. The 15/15 result does not justify claims of real-world accuracy, calibration or language coverage. LLM factuality and retrieval relevance require separate representative evaluation.

## Remaining boundaries

- No guarantee that every possible question, device, failure mode or adversarial input is covered.
- No real approved school data, payments, admissions submission or live support handoff.
- Regex contact redaction is incomplete; SQLite is not encrypted; logical deletion is not secure forensic erasure.
- Shared-token, single-school auth and single-process limits are staging/demo choices, not production multitenancy.
- Provider availability/quota/model access can change. Last success is timestamped/process-local, not a future availability guarantee.
- Dependency upgrades removed the deprecation warnings observed in the earlier delivery. The current pinned environment passed, but future upgrades still require regression checks.
- GitHub Actions was executed after publication: backend 3.11, backend 3.13, frontend and browser jobs passed. Docker and cloud deployment remain unverified.

## Evidence files

- `artifacts/pytest-output.txt`
- `artifacts/coverage.json`
- `artifacts/live-provider-check.json`
- `artifacts/browser-check.json`
- `artifacts/browser-resilience.json`
- `artifacts/evaluation.json`
- `artifacts/experiments.json`
- `artifacts/dependency-audit.json`
- `artifacts/frontend-audit.json`


## v1.2 completion checks

- Added authenticated `/api/operations` and a responsive monitoring panel. Verified empty/no-key, unverified, verified and error states; aggregate p95/fallback metrics; database failures; and absence of credentials/conversation text in the operational response. UI monitoring uses no extra Gemini request.
- Fixed the live diagnostic to choose an available reference/question pair instead of indexing the third FAQ. A one-reference/reordered-knowledge regression passes.
- Added backup/restore tests for rows and feedback, source independence, permissions, integrity, overwrite/symlink refusal, atomic publication races, missing/foreign databases, deadline cleanup and CLI errors.
- The actual live database was snapshotted to a temporary private file and restored to another new file. All 20 records in that snapshot, every column and feedback matched; the original was not replaced, and temporary copies were removed. Evidence: `artifacts/backup-restore-check.json`.
- Browser resilience group 12 verifies protected monitoring and clearing it when analytics locks. The API reference now has 13 endpoints.
- Re-ran all 8 live Gemini FAQ mode/source/intent checks and the unsupported-query check after the revision: passed.
- Measured backend coverage is now 99.74%; the defensive backup integrity-rejection branch was not forced. This explicit unexercised branch does not imply a known functional failure, and coverage is not a no-bug guarantee.

See `PDF_COMPLETION_AUDIT.md` for exact PDF coverage and production tasks that require external input.


## GitHub pre-push clean-checkout verification

The final check was repeated from a separate clean repository folder without the private `.env`, runtime database or developer caches. This caught a test-runner import-path issue that could break a direct `pytest` invocation in CI. Added an explicit project-root `pythonpath` in pytest configuration and changed CI to `python -m pytest`; both entry points now pass from the clean checkout. No live credential is required for the offline suite.

Runtime `.env` variants, credentials, private-key files, databases/backups, artifacts and dependency caches are excluded from Git. The staged source was scanned for the supplied credentials and common token/private-key patterns before publishing.


## Verified GitHub publication

Repository: https://github.com/rutsav075-sudo/Internship-1  
Initial application commit: `11f5cb2074e6db534ec54eb21a960f644a5a6f28`  
Remote CI evidence: https://github.com/rutsav075-sudo/Internship-1/actions/runs/41166106161

All four GitHub jobs concluded **success**: backend (3.11), backend (3.13), frontend and browser. This verifies the published source in clean remote runners; it is not a production deployment or a zero-defect guarantee. Secrets, the runtime `.env`, databases/backups, generated artifacts and dependency directories were not committed.
