# Edxso Education AI · v1.2

A working school FAQ assistant and conversational analytics workspace, aligned with the attached **AI Engineer Intern** job description. Python/FastAPI backend, scikit-learn NLP, server-side Gemini, SQLite and a responsive browser UI.

> **Scope:** The PDF is an internship job description, not a project specification. The user approved this education assistant + analytics project and selected Gemini. This is an independent demonstration, not an official Edxso product or a real school's admissions system.

## Verified delivery status — 31 October 2026

- **151 automated tests passed**, with no warnings in the final test run.
- **99.74% measured backend statement/branch coverage** under coverage.py. Coverage is evidence of exercised code, **not** proof that the software is defect-free.
- **8/8 real Gemini FAQ checks passed** for response mode, expected first retrieved reference and expected intent category; an unsupported query returned `no_match`.
- Desktop/mobile workflow tests passed with both live Gemini and an isolated no-key server.
- **12 browser resilience checks passed**, including injected network/storage failures, double-submit prevention and lock-during-request behavior.
- All five screens checked at widths **320, 390, 768, 1024 and 1440** without horizontal overflow.
- Ruff, ESLint and Prettier checks passed. Python compilation passed.
- `pip-audit` on production requirements and `npm audit` on frontend tooling reported **no known vulnerabilities** at check time. These are advisory scans, not security certifications.
- Docker/cloud deployment, sustained load tests and independent security review have **not** been performed.

## What changed in v1.2

- Completed a fresh review of all 3 PDF pages; see the final responsibility-by-responsibility audit.
- Added a protected operational monitoring panel/API with database status, model fingerprint, provider state, p95 answer time and fallback share. Monitoring does not invoke Gemini.
- Added consistent online SQLite backups and safe restore-to-new-file tooling; verified against a snapshot of the actual preview database without replacing or modifying the live original.
- Fixed the connection-test assumption that FAQs have a particular order/minimum length; a single-reference regression now passes.
- Added isolated no-key browser checks to CI configuration; local equivalent passed, remote CI has not been executed here.
- Updated the operations runbook, tests and source-package exclusions. See [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md).

## What changed in v1.1

1. **Fixed a real provider compatibility issue.** The original `gemini-2.5-flash` generation endpoint returned HTTP 404 for this account. The supplied key successfully generated with `gemini-3.1-flash-lite`, which is now the configured/default model. This is a verified accessible model, not a claim that it is the newest model.
2. **Stronger Gemini integration.** Reused HTTP connection pool, total request deadline, bounded generation slots, bounded queue wait, typed/sanitized failure categories, rejection of truncated/blocked/empty responses, and a 60-second cooldown after credential/model/quota failures.
3. **Actual connection diagnostics.** Admin-only status and live-test endpoints, with a **Test live Gemini** button. A configured key is never presented as proof of generation success.
4. **Stricter API boundary.** Explicit request/response schemas; unknown fields rejected; ratings must be integers `-1` or `1`, not booleans/strings; 16-KiB body limit including chunked requests; validation errors do not echo supplied values.
5. **Correct Bearer authentication.** Protected endpoints use an OpenAPI security scheme, constant-time secret comparison, and `WWW-Authenticate` responses.
6. **More reliable storage.** Schema migration for existing databases, sanitized 503s on SQLite failure, SQL analytics rather than loading all events into Python, bounded recent results, paginated history, consistent-read streaming CSV export, p95 latency and answer-mode aggregates.
7. **Improved synthetic training coverage.** Added 75 labelled examples, retaining the original 15-example test partition. All eight canonical FAQs now have the expected intent, including the previously incorrect school-timings question.
8. **Frontend fixes.** Safe handling of unknown/prototype hash routes, request deadlines, recoverable errors, double-submit prevention, accessible menu/busy states and protection against in-flight analytics restoring data after locking.
9. **Repeatable quality checks.** Offline-by-default test fixtures, mocked provider failures, browser fault injection, formatting/lint configuration and GitHub Actions configuration.

See [PDF_COMPLETION_AUDIT.md](PDF_COMPLETION_AUDIT.md), [TEST_REPORT.md](TEST_REPORT.md), and [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md).

## Features

- Source-backed assistant for admissions, fees, academics, transport and support.
- Transparent `gemini`, `retrieval` and `no_match` modes; no fake LLM answers.
- FAQ browser with live search and an ask-this-question action.
- Predicted intent, uncalibrated model score, retrieved sources, server answer time and helpfulness feedback.
- Admin dashboard with actual stored counts, sessions, intent breakdown and recent conversations.
- Streaming CSV export with spreadsheet-formula neutralization.
- Confirmed deletion of all conversation records and feedback.
- Reproducible model evaluation and word-versus-character feature experiments.
- Contact-school checklist that clearly states **no live contact or ticket service is configured**.
- Self-contained API reference at `/docs`, machine-readable OpenAPI at `/openapi.json`.

## Run locally

Verified here on **Python 3.13.16**. Use Python 3.13 for the closest match to the tested environment. The CI configuration also targets 3.11, but that remote job has not been executed here.

```bash
git clone https://github.com/rutsav075-sudo/Internship-1.git
cd Internship-1
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m scripts.setup
```

Setup creates a private `.env` with a random admin token, without overwriting existing credentials. Edit it locally:

```dotenv
GEMINI_API_KEY=YOUR_OWN_KEY
GEMINI_MODEL=gemini-3.1-flash-lite
ADMIN_TOKEN=KEEP_THE_GENERATED_RANDOM_TOKEN
PROVIDER_TIMEOUT_SECONDS=30
PROVIDER_CONCURRENCY=8
CHAT_RATE_LIMIT=20
```

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

Open `http://localhost:8000`. Node/npm are **not required to run** the application. If using the downloaded ZIP instead of Git, extract it and run the same setup commands from its `edxso-ai` folder; do not clone a second copy.

### Existing live preview

The supplied Gemini key is configured **server-side only** in `/home/user/edxso-ai/.env`, with restricted file permissions. Real generation has been verified. The downloadable archive deliberately contains **no key, admin token or conversation database**.

The same `.env` contains the workspace `ADMIN_TOKEN`. Copy it locally into **Settings & connection → Analytics access**. It stays in browser memory and is cleared on page reload. The server token is distinct from the Gemini key: **do not use the Gemini key as the dashboard password**.

The live database includes synthetic QA conversations created during actual tests. They are not fabricated dashboard metrics. Existing conversations were not blanket-deleted during this revision; destructive checks used an isolated database.

**Rotate the Gemini credential shared in chat after testing.** Replace it in `.env` and restart the server. Secrets are read at startup; editing the file does not hot-reload the running configuration.

### Without a key

Supported questions return the top reference FAQ verbatim, labelled **Reference FAQ**. Unmatched questions return **No source match**. Analytics, classification, feedback and export remain testable without paid LLM access.

## Architecture

```text
Browser (relative, same-origin requests)
  → FastAPI: body bound → validation → client rate limit
    → contact-detail redaction
    → TF–IDF + Logistic Regression → predicted intent + model score
    → FAQ cosine retrieval → up to 3 references
    → optional Gemini generation (bounded queue / deadline)
       → typed provider failure → labelled reference fallback
    → SQLite persistence (threadpool offload for chat writes)
    → protected SQL analytics / paginated history / streamed export
```

Modules:

| File | Responsibility |
|---|---|
| `app/config.py` | Immutable validated settings; secret-free representations |
| `app/schemas.py` | Input/output contracts and FAQ validation |
| `app/ml.py` | Dataset validation, classifier, retrieval and evaluation |
| `app/provider.py` | Gemini adapter and sanitized failure categories |
| `app/diagnostics.py` | Process-local provider success/failure status and cooldown |
| `app/limits.py` | Bounded in-memory limiter and ASGI body-size protection |
| `app/privacy.py` | Best-effort contact redaction and CSV neutralization |
| `app/store.py` | SQLite access, migration, SQL aggregation and export iteration |
| `app/monitoring.py` | Read-only protected operational snapshot without extra AI calls |
| `app/backup.py` | Consistent, integrity-checked private snapshots and non-overwriting restore |
| `app/main.py` | Composition, lifespan management, auth, routes and error handling |
| `app/static/` | UI, styles, JavaScript and self-contained API docs |

Only the current redacted question and retrieved references go to Gemini. Earlier messages are **not** sent. This is a single-turn FAQ assistant with a conversational display, not a multi-turn autonomous agent. Source lists are retrieved context, not verified sentence-level citations. Gemini may still make mistakes; prompt instructions are not a formal grounding or prompt-injection defense.

## Database connection

The running preview is connected to its persistent SQLite database, with an explicit `DATABASE_PATH` in the private server configuration. Independent write/read, live API, feedback and CSV checks passed; only the unique verification record was removed afterwards. See [DATABASE_CONNECTION.md](DATABASE_CONNECTION.md) for the connection details and deployment guidance.

## Data, training and measured evaluation

- `data/faqs.json`: **8 illustrative references**, not official Edxso or real school policies.
- `data/training.json`: original **60 synthetic English examples**, 12 per category.
- `data/augmentation.json`: **75 additional synthetic examples**, 15 per category.
- Total serving corpus: **135 examples**.
- Training validates class names, minimum counts, nonempty strings and exact duplicates; augmentation cannot exactly duplicate original examples. FAQ IDs must be unique.
- FAQ retrieval indexes questions and keywords, avoiding repeated generic disclaimer text in answers.

Classifier: word TF–IDF, unigrams/bigrams, English stop-word removal, sublinear frequency; Logistic Regression `C=4`, maximum 1,000 iterations, seed 42.

Evaluation preserves the original stratified **45/15** split. The 75 added examples are appended **only to evaluation training**: **120 train / 15 test**. Feature extraction fits training data only. Serving separately fits all 135 examples. Dataset SHA-256 is included in the evaluation artifact for traceability.

Current measurements:

| Measurement | Result | Interpretation |
|---|---:|---|
| Fixed small synthetic test | 15/15 correct; macro F1 1.000 | Not a production or fresh independent benchmark |
| Word features, stratified 3-fold CV on 135 examples | Accuracy 0.7481; macro F1 0.7481 | More variation than the tiny fixed test reveals |
| Character features, same 3-fold splits | Accuracy 0.8000; macro F1 0.7923 | Experimental alternative, not silently switched into serving |

The original baseline scored 8/15 before augmentation. This is an iterative, development-observed synthetic test, **not a newly untouched independent validation set**. Exact-duplicate prevention does not eliminate semantic similarity between hand-written paraphrases. Do not interpret the 15/15 result, model scores, or test-code coverage as a real-world accuracy promise. Collect representative consented data and a new untouched evaluation set before production.

## Development checks

```bash
pip install -r requirements-dev.txt
ruff check app scripts tests
ruff format --check app scripts tests
python -m pytest -q --cov=app --cov-fail-under=95
python -m scripts.evaluate
python -m scripts.experiment
```

The automated suite is deliberately **offline**, with explicit no-key settings and a network-blocking fixture. It cannot accidentally use credentials from a developer's `.env`.

Optional frontend tooling requires Node **20.19+**, 22.13+, or newer supported LTS:

```bash
npm ci --ignore-scripts
npm run lint
npm run format:check
```

GitHub Actions config runs lint, format, tests, coverage, evaluation, experiments and isolated no-key browser checks; it has not been uploaded or executed remotely in this workspace.

### Offline browser regression checks

```bash
python -m playwright install --with-deps chromium
# In a separate terminal, use a DISPOSABLE database and explicitly disable Gemini:
GEMINI_API_KEY='' DATABASE_PATH=/absolute/path/browser-test.sqlite3 \
  uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 1

TEST_BASE_URL=http://127.0.0.1:8001 TEST_ALLOW_DELETE=true python -m scripts.browser_check
TEST_BASE_URL=http://127.0.0.1:8001 python -m scripts.browser_resilience
```

The first script's deletion branch requires `TEST_ALLOW_DELETE=true` and deletes **all records on that test server**. Never enable it against real data. The resilience script refuses a server with a configured Gemini key. It deliberately injects failing HTTP/network responses, so those failures are expected test conditions.

Windows: set the environment variables in PowerShell rather than using shell-prefix syntax. Browser scripts use the local `.env` admin token unless `TEST_ADMIN_TOKEN` is explicitly set.

### Opt-in live provider checks

These use API quota and store synthetic chat records:

```bash
python -m scripts.live_check --allow-api-usage
TEST_ALLOW_API_USAGE=true TEST_EXPECT_MODE=gemini python -m scripts.browser_check
```

`live_check` also performs one admin diagnostic generation that does not store a conversation. Its report is `artifacts/live-provider-check.json`. A live failure causes the script to fail; an FAQ fallback is not treated as a Gemini success.

## API and operational behavior

There are 13 documented endpoints. See `/docs` and `/openapi.json` for the contract.

- Public: health, readiness, approved demo knowledge, model metrics and rate-limited chat.
- Session-capability scoped: feedback requires the message's originating session UUID.
- Admin: analytics, paginated history, export, deletion, provider status, live check and operational monitoring.
- Chat: default 20 requests/client/minute, `Retry-After` on 429.
- Live diagnostic: 3 requests/client/minute, separately limited.
- Provider connection pool: default 8 concurrent generations, 3-second queue wait and 30-second total generation deadline.
- Authentication/model/quota failures pause automatic calls for 60 seconds. Admin testing can bypass this cooldown, within its own rate limit. There are **no automatic charged-generation retries**.
- Common failures are sanitized into controlled categories. No raw provider errors, request headers or credentials are returned to clients or written into app logs.
- Provider status/counters and rate limits are process-local and reset on restart.
- Response-time metrics measure server answer processing before persistence, excluding browser/network time. They are not browser end-to-end latency measurements.
- SQL daily aggregates are UTC and bounded to the last 30 active dates. All-time totals still cover all stored records.

## Privacy and security limitations

- Common emails and phone-like numbers are redacted before external generation and server storage. This is a regex-based convenience, **not comprehensive DLP**; it can miss or over-redact data.
- The original question is still visible in the current browser session. Refresh clears the chat display, not stored server records.
- SQLite is not encrypted by this app. Deletion is logical row deletion, **not forensic erasure** of database pages/WAL/backups.
- Knowledge/evaluation/health/chat are public. Do not put private institutional content in the public FAQ endpoint.
- Feedback session UUIDs are capabilities, not authenticated user accounts.
- Admin auth is a single-school shared token, not institutional SSO/RBAC or tenant isolation.
- The limiter uses direct client IP, not arbitrary forwarded headers. Behind a proxy users may share an address. Configure trusted proxies and shared edge limits before public deployment.
- No automatic retention policy, audit trail, consent workflow or legal-compliance certification is supplied.
- Google receives the redacted current question and references when Gemini is enabled. Review applicable provider data terms before using real school information.
- The application has no automatic proof of answer factuality or comprehensive jailbreak defense.

## Staging and deployment

Dockerfile uses Python 3.13, a non-root user and `/api/ready` health checks. The image was **not built or run here** because Docker is unavailable in this environment.

```bash
docker build -t edxso-ai .
docker volume create edxso-data
docker run --rm -p 8000:8000 --env-file .env \
  -v edxso-data:/app/data edxso-ai
```

Use one worker and a persistent volume for this SQLite demo. A newly created Docker named volume should inherit ownership from `/app/data`; bind-mounted host directories require explicit permission checks. Set `DATABASE_PATH` to an absolute persistent path if you change the mount layout. `/api/ready` validates a database read and loaded models; it does **not** prove write permission or external Gemini availability.

The app binds `0.0.0.0`; all browser requests are relative URLs and work with proxied previews. For a managed container host, use port 8000, inject secrets through its secret manager, attach persistent storage and terminate HTTPS at the platform/reverse proxy. No cloud resources were created.

Before production:

1. Replace sample FAQs with approved institutional content; restart after edits.
2. Train/validate on representative, consented enquiries with a new untouched test set; assess OOD behavior, calibration, language coverage, retrieval and answer factuality separately.
3. Add institutional identity/RBAC, tenant isolation and audit logs.
4. Add edge/shared rate limits, budget controls, backpressure, load tests and external monitoring/alerts.
5. Establish consent, retention, backups, restore tests and incident-response procedures.
6. Review privacy obligations and provider data-handling terms.
7. Build/scan the image, verify volume permissions and run staging smoke tests.
8. Configure real school contacts/handoff only after approval.

No software can honestly be promised “errorless” or “bug-free.” This is a substantially tested and improved demo with explicit boundaries, not a production certification.
