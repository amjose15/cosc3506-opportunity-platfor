Chosen challenge: R4-20 — Interest survives synchronisation
# COSC3506 Project 2 — Final Release Submission

- **Team:** team-06
- **Project:** Opportunity Registry and Pathway Platform
- **Chosen challenge:** R4-20 — Interest survives synchronisation

## Assessed Release

- **Release:** FINAL
- **Branch:** `final-release`
- **Release tag:** `FINAL-submission`
- **Full commit SHA:** `ff580cd314f7e9904e922e32b1075e512130d172`
- **Repository:** https://github.com/amjose15/cosc3506-opportunity-platfor
- **Deployment:** https://cosc3506-final-release.onrender.com

## Application Overview

The Opportunity Registry and Pathway Platform provides a unified platform for discovering opportunities, faculty projects, external opportunities and managing student and faculty workflows.

The application includes:
- Unified opportunity discovery.
- External opportunity synchronization.
- Faculty and student workflows.
- Faculty interest management.
- Intake and lifecycle management.
- Evaluation and verification support.

## External Source and Synchronization

The application uses the supplied synthetic Mitacs demonstration feed.

The synchronization process supports:
- Importing external opportunities.
- Updating existing records.
- Handling missing records.
- Reporting malformed records.
- Preserving local faculty interest during synchronization.

The application does not connect to a live Mitacs service.

## Evaluator Accounts

The prototype uses course demo identity headers rather than institutional authentication.

- **Operator:** admin@algomau.ca
- **Verified faculty:** f-alex@algomau.ca
- **Additional faculty:** f-priya@algomau.ca, f-jordan@algomau.ca, f-mei@algomau.ca
- **Student:** s01@algomau.ca

## Reviewer Test Access

Reviewers can use the following demo identities:

- Faculty: f-alex@algomau.ca
- Student: s01@algomau.ca
- Operator: admin@algomau.ca

The prototype uses demo identity selection and does not require institutional passwords.

Operator synchronization endpoints require the appropriate demo identity header.

## Deployment

The final application is deployed on Render.

**Deployment URL:**
https://cosc3506-final-release.onrender.com

## Known Issues and Limitations

- The external provider feed is synthetic.
- Demo sign-in is not production authentication.
- SQLite persistence depends on Render filesystem configuration.
- Operator synchronization and health functions are available through documented API routes.
- Full cumulative regression testing should be verified against the Final Release requirements.

## Freeze Evidence

- **Branch:** final-release
- **Tag:** FINAL-submission
- **Commit SHA:** ff580cd314f7e9904e922e32b1075e512130d172
- **Deployment:** https://cosc3506-final-release.onrender.com
