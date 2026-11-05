# Project 2 — Release 3 Submission

## Assessed release
- **Release tag:** `R3-submission`
- **Full commit SHA:** 1c4212d9c7098782864702b112465fa7caea3eb1
- **Deployed URL:** https://student-academic-history-api-u1zk.onrender.com
- **Health check:** `/api/r3/health` should return `status: ok` and `release: R3-submission`.

## Fixture loading and clock
- Both official files are committed under `data/`: `lifecycle_fixture.json` and `expected_lifecycle_results.json`.
- The application imports `lifecycle_fixture.json` idempotently during startup after the R1/R2 and R3 schema migrations. It maps fixture faculty/student IDs to synthetic `@algomau.ca` accounts, opportunities to existing `projects`, and matches/outcomes to the R3 tables.
- `expected_lifecycle_results.json` is acceptance criteria only. The application does not import it as product records; `verify_r3_fixture.py` compares the loaded database state against it.
- The fixture declares `evaluation_date: 2026-11-06`. `r3_effective_date()` reads that value and lifecycle expiry uses it instead of the host clock. `/api/r3/health` reports the simulated date. If the fixture is absent, the app falls back to the server's current date.
- Re-run fixture verification from the repository root with `python verify_r3_fixture.py` after the application has initialized its SQLite database.

## Evaluator setup
Demo accounts:
- Faculty: `f-alex@algomau.ca`, `f-priya@algomau.ca`, `f-jordan@algomau.ca`, `f-mei@algomau.ca`
-  Unverified faculty: `u-pending@algomau.ca`
- Fixture students: `s01@algomau.ca`, `s05@algomau.ca`, `s08@algomau.ca`, `s11@algomau.ca`, `s17@algomau.ca` (plus `s02@algomau.ca` for completed-work outcomes).
- Staff: `admin@algomau.ca`

The demo authentication mode is not production authentication. Use synthetic test accounts only. Sign-in does not use passwords.

## Required QA setup
Prepare at least one opportunity in each state: Active, Expired, Withdrawn, Matched, Completed and Archived. Prepare one multi-student proposal where two students confirm independently; one proposal declined; and one withdrawn by faculty. Prepare one outcome confirmed by participating verified faculty with all required public consents, and one outcome awaiting faculty confirmation.

## Routes
See `evaluation_adapter.json` for match proposal/response/withdrawal, lifecycle, renewal, partner agreement, outcome reporting/confirmation/consent, public showcase, and profile outcome routes.

## Known issues / limitations
- The demo `X-Demo-Email` identity mechanism is not institution-backed authentication and is suitable only for the course prototype.
- SQLite is used. Confirm the Render filesystem/database persistence configuration before relying on deployed data across restarts.
- The R3 API workflows are implemented; evaluator workflows can be exercised through the documented API routes. Some administrative lifecycle and outcome operations may require API tooling rather than complete guided frontend forms.
- Full end-to-end R1/R2 regression testing and deployed QA remain required before claiming all cumulative requirements pass.

## Freeze evidence
- Tag: `R3-submission`
- Commit SHA:1c4212d9c7098782864702b112465fa7caea3eb1
- QA issues and fixes: TO BE RECORDED
