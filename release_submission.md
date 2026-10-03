## Fixture loading

The official `r1_fixture.json` file is stored in the `data/` directory. The application loads the fixture automatically when the FastAPI application starts. This initializes the required Release 1 research areas, faculty records, projects, and account states.

## Evaluator accounts

The following demo accounts are available for Release 1 evaluation:

* **Student:** `student@algomau.ca`
* **Verified faculty:** `f-alex@algomau.ca`
* **Unverified faculty:** `u-pending@algomau.ca`
* **Staff/Admin:** `admin@algomau.ca`

No passwords or long-lived secrets are required for these demo accounts.

## Public/private checks

* Logged-out users can view public faculty profiles and public published projects.
* Logged-out users cannot view private faculty profiles or authenticated-only projects.
* Authenticated users can access appropriate private faculty/project information.
* Unverified faculty are not displayed as verified faculty in discovery.
