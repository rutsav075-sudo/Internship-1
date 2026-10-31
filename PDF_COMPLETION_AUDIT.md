# Final PDF completion audit · v1.2

**Source reviewed:** all 3 pages of `Job Description_ AI Engineer Intern.docx.pdf`.  
**Scope:** the education assistant + analytics project approved by the user, with Gemini and SQLite.  
**Review date:** 31 October 2026.

## What the PDF actually asks for

The attachment is an **AI Engineer Intern job description**, not a software assignment. It does not specify screens, a database vendor, a cloud account, a dataset, authentication rules or acceptance tests. The project below demonstrates its engineering responsibilities without claiming that every job-description sentence is a software feature.

## Seven key engineering responsibilities — checked individually

| PDF responsibility (page 2) | Implemented evidence | Verification / status |
|---|---|---|
| Design, train and evaluate classification, NLP or conversational analytics models | Validated synthetic dataset, TF–IDF/Logistic Regression, reproducible evaluation, per-class report and confusion matrix | Implemented and tested; serving fits 135 synthetic examples. The fixed 15-example test is development-observed, not an independent real-world accuracy claim. |
| Integrate AI into backend services and user-facing platforms | FastAPI, server-only Gemini integration, responsive assistant and analytics UI, persistent SQLite | Implemented; all 8 canonical FAQ live-generation/source/intent checks passed. Actual database write/read, feedback and export checks passed. |
| Feature engineering, model testing and iterative refinement | Word n-grams/stop words/sublinear TF–IDF, validated augmentation, fixed original test partition, model fingerprints and word-vs-character experiments | Implemented and tested. Earlier fee/timings regressions were corrected and retained as regression checks. |
| Write modular code and documentation | Separate configuration, schemas, ML, provider, storage, limits, privacy, monitoring and backup modules; API docs and runbooks | Implemented. Ruff, ESLint, formatting, Python compilation and automated tests pass. |
| Deploy to staging and monitor performance | Running preview/staging-style service, readiness endpoint, Docker recipe, protected operational monitoring UI/API, p95/answer-mode/fallback metrics and provider timestamps | Preview verified. Added monitoring in v1.2. Docker/cloud deployment has **not** been executed; a hosting account/target is still needed for actual external deployment. |
| Research and experiment with new ML techniques | Reproducible stratified 3-fold word-versus-character feature comparison | Implemented and rerunnable. Alternative results are reported honestly; serving is not silently changed based on a tiny benchmark. |
| Troubleshoot and debug development/testing issues | Provider compatibility fixes, strict API validation, auth, redaction, error handling, rate/queue/body limits, browser fault injection and database tests | **151 automated tests pass**, **99.74% measured backend coverage**; desktop/mobile workflow and **12 browser resilience groups** pass. Coverage does not prove zero bugs. |

## Required skills — what this project demonstrates

- **Python and an ML library:** implemented in Python with scikit-learn. The PDF says scikit-learn, TensorFlow **or** PyTorch; it does not require all three.
- **Preprocessing/evaluation:** validated data, TF–IDF pipelines, no feature-fitting on evaluation test examples, per-class metrics, confusion matrix and cross-validation experiments.
- **NLP/conversational AI:** intent classification, source retrieval and real Gemini generation with transparent reference fallback.
- **Clear communication:** written architecture, setup, API documentation, traceability and explicit limitations. This does not replace an applicant's verbal interview.
- **Degree eligibility, eagerness, teamwork and hybrid availability:** these are applicant qualifications; software cannot certify them.

## Preferred qualifications — not falsely treated as mandatory features

- **NLTK/spaCy/Hugging Face:** examples of optional NLP libraries. This implementation uses scikit-learn; these libraries are not claimed as used.
- **AWS/GCP/Azure:** optional cloud familiarity. A deployable container recipe and staging instructions are supplied, but no cloud account or infrastructure was fabricated.
- **APIs/microservices:** model-serving APIs, OpenAPI Bearer security and self-contained documentation are implemented.
- **Data pipelines/experimentation:** versioned training files, validation, deterministic experiments, dataset fingerprints and automated quality checks are implemented.

## Concrete gaps closed in this pass

1. **Operational monitoring:** added an admin-only **Workspace operations** panel and `/api/operations`, showing database connection, model data fingerprint, provider status, p95 answer time, fallback share and process uptime. Monitoring does not make extra paid Gemini calls. It explicitly distinguishes persisted traffic from process-local counters and does not claim external APM/alerting.
2. **Backup/restore workflow:** added an offline administrative CLI using SQLite's consistent online backup API. It checks integrity, protects file permissions on POSIX, rejects overwrites/symlink destinations, uses a progress deadline and only restores to a new file. A restore of the actual preview's snapshot preserved every row/column and feedback; temporary copies were removed and the live original was not replaced.
3. **Real diagnostic bug:** removed an assumption that the FAQ list always has at least three items in a fixed order. Live checks now use an existing reference and its matching question; a one-reference/reordered-data regression test passes.
4. **Repeatable browser checks:** added isolated no-key browser testing to CI configuration, including controlled deletion of only the disposable CI database. The local equivalent was run successfully. The published GitHub Actions browser job has now also passed, alongside frontend and both Python backend jobs.
5. **Delivery protection:** updated packaging exclusions for SQLite/backup files and retained scans preventing the configured credentials from being included in downloads.

## Page 1 and page 3 statements that are not app requirements

- Organisation mission, academic outcomes, leadership and sustainable growth: the app is education-focused, but it does not claim measured institutional/academic outcomes.
- Delhi hybrid/Saturday attendance, 6-month term, ₹7,000 stipend, academic-year eligibility and selection assignment: employment conditions, not software functionality.
- Collaboration and mentorship: human/organisational activities, not a chatbot feature.
- Full-time conversion, internship certificate and professional reference: organisational benefits. The project cannot grant or guarantee them.

## What is complete and what still needs external input

**Complete within the approved demo scope:** the assistant, real Gemini integration, local classification/retrieval, persistent database, feedback, protected analytics/export/deletion, evaluation/experiments, operational monitoring, backup/restore tooling, tests and documentation. The updated app is running in the preview.

**Not claimed complete for real production use:**

- A new permanent cloud deployment needs your hosting choice/account and approved deployment configuration.
- Official school policies, fee schedules and contact/handoff details must come from the school; sample data is still clearly labelled.
- Representative consented training/evaluation data, independent security review, load tests, institutional SSO/RBAC, retention/compliance procedures and external alerting remain production-readiness work.
- The Docker image is supplied as a recipe but was not built/run in this environment.

No remaining sentence in the PDF justifies inventing credentials, cloud infrastructure, school facts or internship outcomes. This audit does not promise bug-free software.

## Evidence

- `TEST_REPORT.md`
- `REQUIREMENTS_TRACEABILITY.md`
- `DATABASE_CONNECTION.md`
- `OPERATIONS_RUNBOOK.md`
- `artifacts/pytest-output.txt`, `coverage.json`, `live-provider-check.json`
- `artifacts/browser-check.json`, `browser-resilience.json`
- `artifacts/database-check.json`, `backup-restore-check.json`
