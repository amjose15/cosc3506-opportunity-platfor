# Project 2 — Release 2 Submission

## Assessed release
- **Release tag:** `R2-submission`
- **Full commit SHA:** `c5740b065a5937e18e6387fff7f3b727b04fe78d`
- **Deployed URL:** https://cosc3506-opportunity-platfor.onrender.com
- **Health check:** https://cosc3506-opportunity-platfor.onrender.com/api/health should return `{"status":"ok","release":"R2-submission"}`.
## Fixture loading
The three supplied Project 2 Release 2 fixture files are stored in `data/`:
- `intake_submissions.json`
- `faculty_subscriptions.json`
- `expected_intake_outcomes.json`

The app loads valid intake and subscription fixtures at startup after loading the Release 1 fixture. Submissions missing organisation, contact email, or title are skipped. `expected_intake_outcomes.json` is retained as acceptance criteria and is not imported as opportunity data.

## Evaluator setup
Demo-mode accounts use `@algomau.ca` addresses:
- Student: `student@algomau.ca`
- Verified faculty: `f-alex@algomau.ca`, `f-priya@algomau.ca`, `f-jordan@algomau.ca`, `f-mei@algomau.ca`
- Unverified account: `u-pending@algomau.ca`
- Staff/admin: `admin@algomau.ca`

This is a course demo authentication mode, not production identity verification. No passwords or long-lived secrets are needed for these test accounts.

## Notifications
Notifications are delivered in the in-product **Notifications** list. To observe them, sign in as a verified faculty demo account and open Notifications. The provided subscriptions fixture is loaded at startup. Faculty can edit subscriptions under **Notification Settings**.

## Key routes
See `evaluation_adapter.json` for the intake surface, faculty willingness/withdrawal actions, engagement updates, subscription settings, notifications, student discovery, and Release 1 regression routes.

## Known issues / limitations
- The provided sign-in is a demonstration mechanism; it must be replaced with real institution-backed authentication before production use.
- SQLite is used for this prototype. Confirm the deployment's database persistence configuration before relying on data across redeployments.
- Verify the deployed URL, tag, full commit SHA, fixture loading, and all role-based checks before submitting.
