# COSC-3506 Project 2 — Release 1 MVP

Minimal R1 implementation for Faculty & Project Discovery.

## Stack
- FastAPI backend
- SQLite for local development
- Simple HTML/CSS/JavaScript frontend
- Seed data compatible with the R1 concept
- Render-ready via `render.yaml`

## Run locally
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

## R1 test accounts
This MVP includes a clearly-labelled instructor-approved-test-mode placeholder login flow.
Replace/extend it with your instructor-approved authentication method before final submission.

Demo accounts:
- student@algomau.ca
- faculty@algomau.ca
- admin@algomau.ca

The application enforces the `algomau.ca` domain server-side.

## Important
The provided Moodle `r1_fixture.json` was not included in the material available while creating this starter.
Put the official fixture at `data/r1_fixture.json` and run:
```bash
python seed_fixture.py
```
The seed script accepts common fixture shapes and should be adjusted if the instructor fixture uses different field names.

## Render
Set the service to use:
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`

For final R1, use a persistent database (for example Supabase/Postgres) rather than relying on an ephemeral Render filesystem.
