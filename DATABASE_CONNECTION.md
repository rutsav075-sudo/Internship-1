# Database connection

## Decision

The source PDF mentions backend integration and data pipelines, but does not specify a database vendor. This project's approved scope needs persistent conversations and analytics. **SQLite is connected and is suitable for the current single-school, single-instance demo.** No hosted database, account or new paid service is needed.

This is an existing functional database connection, not an additional database silently created alongside the application. The effective database path has now also been explicitly recorded in the private server `.env`.

## Current preview configuration

- Engine: SQLite (Python's standard `sqlite3` driver)
- Database file: `/home/user/edxso-ai/data/app.sqlite3`
- Connection setting: `DATABASE_PATH` in the private server `.env`
- Journal mode: WAL
- Table: `events`
- Application access: `app/store.py`
- Readiness endpoint: `/api/ready`

Stored fields include the conversation/session identifiers, UTC timestamp, redacted question and answer, predicted intent and model score, answer mode, server latency, retrieved reference identifiers, feedback and sanitized provider error category. Analytics is calculated from these records rather than a mock dataset.

## Connection checks performed

All checks passed against the **running preview and its actual database file**:

1. Database integrity check: `PRAGMA quick_check` returned `ok`.
2. Application readiness returned HTTP 200 with database `ok`.
3. A uniquely identified synthetic probe was written and committed through the application's storage layer.
4. A completely separate SQLite connection read that committed probe, proving on-disk persistence rather than in-memory state.
5. The running application's authenticated conversation endpoint returned the same probe, confirming that it reads the same database file.
6. The live feedback API updated the probe, and an independent database read verified that update.
7. The authenticated CSV export contained the probe.
8. Only that unique probe was deleted afterwards. Existing conversations were not cleared or modified.

Evidence: `artifacts/database-check.json`. No Gemini request or API charge was needed for these checks.

## Access and secrets

SQLite does not require a separate database API key, username or password. Access is controlled by filesystem permissions and the application. Analytics, conversation listing, export and deletion require the separate server `ADMIN_TOKEN`.

The database file and `.env` are not served as public web assets and are excluded from source downloads. This does not mean SQLite is encrypted: protect the host, filesystem and backups appropriately.

## Downloaded project versus the current preview

The download intentionally excludes the live database and credentials. On another machine, run `python -m scripts.setup`, configure credentials locally and start the app. It creates the schema automatically and connects to the new local `data/app.sqlite3` file by default. Existing preview records are not included in that new database.

If deploying with Docker, mount a persistent volume at `/app/data` and use the container path `/app/data/app.sqlite3` if setting `DATABASE_PATH`. Do **not** copy the sandbox's `/home/user/...` database path into a different machine's configuration. See `README.md` for the Docker command and remaining deployment caveats.

For a future multi-school service, multiple application instances or substantially higher concurrent write traffic, plan a PostgreSQL migration with schema migration tooling, per-school isolation, a managed persistent service and suitable backups. No PostgreSQL service or migration is claimed in this delivery.


## v1.2 operational additions

The Settings page now has protected **Workspace operations** monitoring; `GET /api/operations` requires the admin token and does not call Gemini. Use `python -m scripts.database backup --output data/backups/example.sqlite3` for a consistent private snapshot. The restore command only creates a new `.sqlite3` file and never overwrites the active database. See `OPERATIONS_RUNBOOK.md` for the safe stop/configure/restart sequence and privacy limitations. A snapshot/restore of the actual preview database was verified with matching rows and feedback, without replacing the live original.
