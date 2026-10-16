# COSC-3506 Project 2 — Release 2

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
