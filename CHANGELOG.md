# Changelog

## 1.2.0 — 31 October 2026

- Re-read all 3 PDF pages and completed the final engineering-responsibility audit.
- Added protected operational monitoring (database/model/provider/p95/fallback state) and a responsive Settings panel.
- Added a consistent SQLite backup/restore CLI with integrity, overwrite, symlink, permission and deadline safeguards; actual snapshot/restore verification passed.
- Fixed the provider test's hard-coded third-FAQ assumption; supports one-reference/reordered knowledge bases.
- Added isolated no-key browser checks to CI configuration and an operational runbook.
- Expanded regression suite to 151 passing tests, with 99.74% measured backend coverage and 12 browser resilience groups; all 8 live FAQ checks passed again.
- Actual Docker/cloud deployment and production institutional data remain external readiness tasks, not claimed as completed.

## 1.1.0 — 30 October 2026

### Fixed
- Actual Gemini model-access failure discovered by live testing; switched from unavailable 2.5 Flash to verified 3.1 Flash Lite.
- School-timings intent regression via broader labelled synthetic data and all-FAQ tests.
- Non-Bearer auth acceptance, non-strict ratings, oversized/chunked request handling and input-echoing validation errors.
- Unbounded Python-side analytics reads and full-memory CSV export.
- Provider empty/refused/truncated outputs being treated as successful answers.
- Fragile hash routing, unbounded frontend wait, double-submit behavior and private analytics lock races.
- Upstream test deprecation warnings through dependency updates.

### Added
- Validated immutable configuration, explicit API schemas and small purpose-specific modules.
- Provider pool/deadline/queue bounds, sanitized failure categories, cooldown and live diagnostic UI/API.
- Database migration, readiness, pagination, SQL p95/mode aggregates and streaming export.
- 75 labelled training additions, data validation and dataset fingerprints; original fixed test partition retained.
- 132 automated tests, live FAQ checks, browser fault injection and responsive checks.
- Ruff, ESLint, Prettier, CI configuration, separate development requirements and advisory-scan artifacts.

### Boundaries
- Tested demo, not a zero-bug or production certification. Data is synthetic; real school information and a fresh real-world evaluation set are still needed.
- Docker, cloud deployment and a remote CI run were not executed.
