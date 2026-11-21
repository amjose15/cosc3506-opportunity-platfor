Chosen challenge: R4-20 — Interest survives synchronisation

# Project 2 — Release 4 Submission

- **Team:** team-06
- **Project:** Opportunity Registry and Pathway Platform
- **Repository:** https://github.com/amjose15/cosc3506-opportunity-platfor

## Assessed release
- **Release tag:** `R4-submission`
- **Branch:** `release4`
- **Full commit SHA:** `a3066e69747a226527a5ed40e6af1d911e7b026e`
- **Deployed URL:** https://cosc3506-opportunity-platfor-4.onrender.com
- **Health check:** `/api/r4/health` returns `{"status":"ok","release":"R4-submission"}`.

## External source and fixtures
The application uses the supplied synthetic Mitacs demonstration feed. It does not connect to a live Mitacs service and does not collect provider application documents. The three official fixture files are stored in `data/`: `external_source_feed_v1.json`, `external_source_feed_v2.json`, and `expected_sync_results.json`. The expected-results file is acceptance criteria only; it is not imported as opportunity data.

## How to run synchronization
1. Sign in using the synthetic operator account `admin@algomau.ca`.
2. Send `POST /api/admin/external-sync` with JSON `{"feed":"v1"}` and header `X-Demo-Email: admin@algomau.ca`. This loads last week's feed.
3. Send the same endpoint with `{"feed":"v2"}` to apply this week's feed.
4. Run v2 again to verify repeatability; no duplicates should be created.
5. Browse external records at `GET /api/external-opportunities`.

## Failed sync simulation and health
- Simulate a source failure with `POST /api/admin/external-sync/fail`, JSON `{"reason":"Simulated source unavailable"}`, and the operator header. This records a failed run without changing opportunity data.
- Operator sync health: `GET /api/admin/external-sync/health` with the operator header. It reports the last successful run and the last failure/reason.

## Faculty interest (chosen challenge R4-20)
A verified faculty member can record local support using `POST /api/external-opportunities/{id}/interest` with their `X-Demo-Email` header. Interest is stored separately from source-owned opportunity fields and therefore survives source changes, disappearance, and reappearance. To withdraw interest, use `DELETE` on the same route.

## Evaluator accounts
- Operator: `admin@algomau.ca`
- Verified faculty: `f-alex@algomau.ca`, `f-priya@algomau.ca`, `f-jordan@algomau.ca`, `f-mei@algomau.ca`
- Student: `s01@algomau.ca`

The prototype uses the course demo identity header, not institutional authentication.

## External opportunity behavior
- External records are labelled with their source and link to the provider's authoritative record.
- The application treats imported descriptions as plain text and escapes them in the browser. Provider content cannot alter local eligibility, approval, roles, or record state.
- Missing records are marked `not_seen`; last-known content is retained. This differs from an explicit provider withdrawal.
- A malformed record is reported and skipped while valid records in the feed continue to synchronize.
- Local faculty interest is separate from source fields. Local student associations, outcome history and readiness guidance are held in separate local fields and are not updated by the feed adapter.
- Readiness text is guidance only and does not block discovery or provider handoff.

## Known issues / limitations
- The provider feed is synthetic; there is no live Mitacs integration.
- Demo sign-in is not production authentication.
- SQLite persistence depends on the Render filesystem configuration.
- The frontend exposes external opportunity discovery and faculty interest. Operator synchronization and health are available through the documented API routes.
- Full cumulative R1–R3 regression testing and independent R4 workflow verification remain to be completed. The deployed R4 health endpoint has been checked successfully.
## Freeze evidence
- **Release tag:** `R4-submission`
- **Full commit SHA:** `a3066e69747a226527a5ed40e6af1d911e7b026e`
- **Branch:** `release4`
- **Deployment:** https://cosc3506-opportunity-platfor-4.onrender.com
- **Health check:** `/api/r4/health` returned `{"status":"ok","release":"R4-submission"}`.
- 
