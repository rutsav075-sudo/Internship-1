# Operations runbook

## Inspect the running app

1. Open the preview → **Settings & connection**.
2. Unlock using `ADMIN_TOKEN` from the private server `.env`.
3. Select **Refresh monitoring** in **Workspace operations**.
4. Review the database connection, provider state, p95 processing time, reference/no-match share, serving sample count and dataset fingerprint.
5. To verify actual external generation, use **Test live Gemini**. Unlike monitoring refresh, this uses Gemini quota. It does not store a conversation.

`GET /api/operations` is admin-only and performs no external AI request. `GET /api/ready` is public and checks loaded models plus a database read, not database write permissions. A failure reading SQLite returns a sanitized 503. Inspect server-side storage permissions/volume health without exposing raw errors to users.

### Interpret metrics correctly

- **Provider configured** means a key is present, not that it is valid or generation has worked.
- **Verified** means at least one generation succeeded in this server process and no later failure is recorded. It is not a guarantee of future availability; inspect the last-check/success timestamps.
- Provider counters and uptime reset on restart. Conversation counts/latencies come from persisted SQLite records.
- Reference/no-match share includes normal no-key/reference operation, unsupported questions and provider fallbacks. A high value is not automatically a provider error rate.
- p95 is the nearest-rank statistic on stored server answer-processing times, not browser/network end-to-end latency. Very small samples are unstable.
- Synthetic-model accuracy does not measure LLM factuality or real-world school performance.
- No external monitoring, automatic alert delivery or formal SLO system is configured. Integrate your chosen operational platform before production.

## Back up the live SQLite database

Use the administrative CLI on the server, not a public web endpoint:

```bash
python -m scripts.database backup \
  --output data/backups/school-2026-10-31.sqlite3
```

It reads the configured `DATABASE_PATH` from the environment/`.env`. You can explicitly supply `--source /absolute/path/app.sqlite3`.

The CLI uses SQLite's **online backup API**, rather than blindly copying a live WAL-mode file. The copy is integrity-checked and published only when complete. The destination must end in `.sqlite3` and must not already exist. Existing files or symlinks are never overwritten. On POSIX the resulting file has owner-only read/write permissions. Protect the parent directory and host as well.

The backup operation has a 30-second progress deadline, plus SQLite's connection busy handling; a blocked/failed operation returns a nonzero exit status and removes temporary copies. This is not a hard real-time guarantee against kernel/disk failures. Very large databases may require a separately reviewed backup strategy.

**Backups contain conversation data. They are not encrypted by this utility.** Copy to approved secure backup storage, set retention and access controls, and test restoration regularly. No offsite storage or automatic backup schedule is configured.

## Restore safely to a new file

```bash
python -m scripts.database restore \
  --source data/backups/school-2026-10-31.sqlite3 \
  --output data/restored-school.sqlite3
```

The restore command deliberately refuses to replace an existing database. It creates a fresh, integrity-checked copy. It does not change the running app's configuration or swap databases under an active process.

After verifying the restored copy:

1. Stop the running application.
2. Keep a safe backup of the previous live database; do not delete it as part of the switch.
3. Set the private server `DATABASE_PATH` to the restored file's **absolute path on that host**.
4. Restart the service using one worker.
5. Check `/api/ready`, unlock analytics, inspect counts/feedback and perform a synthetic write/read smoke test.
6. For rollback, stop the service and point `DATABASE_PATH` back to the preserved original, then restart.

Do not copy the sandbox's `/home/user/...` path into a Docker container or a different host. Docker's default persistent path is `/app/data/app.sqlite3` with a volume mounted at `/app/data`.

## Check credentials or model failures

- `authentication`: review the private key and API permissions; never paste secrets into frontend code or logs.
- `model_unavailable`: select an accessible model and verify a real generation. The current default `gemini-3.1-flash-lite` was verified with the supplied credential.
- `quota`: inspect provider quotas/billing and rate limits; avoid repeated paid retries.
- `timeout`/`network`/`upstream`: check connectivity/provider availability. Supported FAQ answers remain explicitly labelled fallbacks.
- `blocked`/`truncated`/`invalid_response`: the response was not accepted as a successful answer; a reference fallback is used.

Credentials/model/quota errors pause automatic calls for 60 seconds. The admin test can bypass this cooldown but has its own 3-per-minute client limit. Configuration changes require a restart.

## Staging checks and deployment boundaries

```bash
python -m pytest -q --cov=app --cov-fail-under=95
ruff check app scripts tests
ruff format --check app scripts tests
npm ci --ignore-scripts
npm run lint
npm run format:check
```

For browser checks, use the isolated no-key server instructions in `README.md`. Destructive checks must never target real data. For opted-in live integration, use `python -m scripts.live_check --allow-api-usage`.

A persistent cloud deployment still needs a chosen host/account, TLS, secret manager, persistent volume, trusted proxy/rate-limit policy, backups and production data/security decisions. The preview demonstrates the app running; it is not a substitute for a permanent production deployment or an independent security audit.
