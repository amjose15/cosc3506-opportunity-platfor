# COSC-3506 Project 2 — Release 3

Opportunity Registry and Pathway Platform: faculty/project discovery plus accountless industry intake, faculty willingness, partner-engagement coordination, and area-based in-product notifications.

## Stack
- FastAPI backend
- SQLite storage
- HTML/CSS/JavaScript frontend
- Release 1 fixture: `data/r1_fixture.json`
- Release 2 fixtures: `data/intake_submissions.json`, `data/faculty_subscriptions.json`, and `data/expected_intake_outcomes.json`

## Run locally
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open `http://127.0.0.1:8000`.

## Demo accounts
- Student: `student@algomau.ca`
- Verified faculty: `f-alex@algomau.ca`, `f-priya@algomau.ca`, `f-jordan@algomau.ca`, `f-mei@algomau.ca`
- Unverified: `u-pending@algomau.ca`
- Staff/admin: `admin@algomau.ca`

The current sign-in is a course demonstration mode, not production identity verification. Do not use it for real users or sensitive information.

## Release 2 behaviour
- Partners can submit without signing in.
- New submissions remain pending and do not appear in student discovery until verified faculty willingness exists.
- Verified faculty can volunteer/withdraw, see interest counts and private partner contact details, and record engagement status.
- Faculty can subscribe to all opportunities, selected areas, or none. Notifications are delivered in the in-product Notifications list.
- Partner contact details and engagement information are not returned by student/guest opportunity endpoints.

## Release tag and evidence
Before submission, deploy and test the app, create the immutable `R2-submission` Git tag, and replace the placeholders in `release_submission.md` with the actual deployed URL and full commit SHA. See `evaluation_adapter.json` for the evaluator route/setup map.


## Release 3
R3 adds two-sided match proposals, lifecycle states and deadlines, opportunity renewal, partner agreement recording, outcomes and consent-controlled showcase routes. See `evaluation_adapter.json` for the evaluator route map.

### R3 fixture
Place the official `lifecycle_fixture.json` at `data/lifecycle_fixture.json`. The fixture's `evaluation_date` is used as the simulated current date for expiry evaluation. `expected_lifecycle_results.json` is acceptance criteria only and must not be imported as product data. The fixture import/seed instructions should be completed against the official fixture schema before assessment.

### Demo mode and security
The existing `X-Demo-Email` mechanism is a course prototype and is not institution-backed authentication. Use only synthetic accounts for evaluation; do not use real credentials or secrets.


## Release 3 — Matching, lifecycle and outcomes

The R3 additive schema is initialized at startup. The official synthetic fixture is stored at
`data/lifecycle_fixture.json`; the expected acceptance results are stored separately at
`data/expected_lifecycle_results.json` and are not imported as application data.

The fixture's fixed `evaluation_date` (2026-11-06) is used by lifecycle expiry evaluation.
After startup, run `python verify_r3_fixture.py` from the repository root to compare the
loaded fixture state with the acceptance criteria.

Key API surfaces:
- `POST /api/projects/{project_id}/matches`
- `POST /api/matches/{match_id}/response`
- `POST /api/matches/{match_id}/withdraw`
- `GET /api/matches`
- `GET /api/projects/{project_id}/lifecycle`
- `POST /api/projects/{project_id}/lifecycle`
- `POST /api/projects/{project_id}/renew`
- `POST /api/projects/{project_id}/outcomes`
- `POST /api/outcomes/{outcome_id}/confirm`
- `PUT /api/outcomes/{outcome_id}/consent`
- `GET /api/outcomes`
- `GET /api/profiles/{user_id}/outcomes`
- `GET /api/r3/health`

Match confirmation records intent to collaborate only. It does not constitute academic
eligibility, course registration, credit or university approval.
