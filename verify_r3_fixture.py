"""Verify the R3 fixture import against expected_lifecycle_results.json.

Run from the repository root after the application has initialized data/opportunity.db:
    python verify_r3_fixture.py
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
db = ROOT / "data" / "opportunity.db"
fixture = json.loads((ROOT / "data" / "lifecycle_fixture.json").read_text(encoding="utf-8"))
expected = json.loads((ROOT / "data" / "expected_lifecycle_results.json").read_text(encoding="utf-8"))

if not db.exists():
    raise SystemExit("Database not found. Start the FastAPI app once to initialize and load fixtures.")

con = sqlite3.connect(db)
con.row_factory = sqlite3.Row

projects = {r["fixture_id"]: r["lifecycle_state"] for r in con.execute(
    "SELECT fixture_id, lifecycle_state FROM projects WHERE fixture_id LIKE 'O-%'")}
expired = sorted(k for k, v in projects.items() if v == "Expired")
assert expired == sorted(expected["expired_opportunity_ids"]), (expired, expected["expired_opportunity_ids"])

for oid, reason in expected["past_deadline_but_not_expired"].items():
    expected_state = {"O-301": "Matched", "O-305": "Withdrawn", "O-306": "Completed", "O-307": "Archived"}[oid]
    assert projects.get(oid) == expected_state, (oid, projects.get(oid), expected_state)

still_open = sorted(k for k, v in projects.items() if v == "Active")
assert still_open == sorted(expected["still_open_opportunity_ids"]), (still_open, expected["still_open_opportunity_ids"])

matches = {r["fixture_id"]: r["state"] for r in con.execute(
    "SELECT fixture_id, state FROM matches WHERE fixture_id IS NOT NULL")}
fully = sorted(k for k, v in matches.items() if v == "Confirmed")
partly = sorted(k for k, v in matches.items() if v == "Partly Confirmed")
not_confirmed = sorted(k for k, v in matches.items() if v not in ("Confirmed", "Partly Confirmed"))
assert fully == sorted(expected["fully_confirmed_match_ids"]), fully
assert partly == sorted(expected["partly_confirmed_match_ids"]), partly
assert not_confirmed == sorted(expected["not_confirmed_match_ids"]), not_confirmed

public_outcomes = []
participants_only = []
for row in con.execute("""SELECT o.fixture_id, o.faculty_confirmed, u.public_profile
    FROM outcomes o JOIN users u ON u.id=o.faculty_user_id WHERE o.fixture_id IS NOT NULL"""):
    consents = [x["public_consent"] for x in con.execute(
        "SELECT public_consent FROM outcome_consents WHERE outcome_id=(SELECT id FROM outcomes WHERE fixture_id=?)",
        (row["fixture_id"],))]
    eligible = bool(row["faculty_confirmed"] and row["public_profile"] == 1 and consents and all(x == 1 for x in consents))
    (public_outcomes if eligible else participants_only).append(row["fixture_id"])
assert sorted(public_outcomes) == sorted(expected["showcase_eligible_outcome_ids"]), public_outcomes
assert sorted(participants_only) == sorted(expected["participants_only_outcome_ids"]), participants_only

con.close()
print("R3 fixture verification PASSED")
print("Evaluation date:", fixture["evaluation_date"])
print("Expired:", expired)
print("Active discovery:", still_open)
print("Fully confirmed matches:", fully)
print("Partly confirmed matches:", partly)
print("Public showcase:", sorted(public_outcomes))
print("Participants only:", sorted(participants_only))
