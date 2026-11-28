"""Focused R4-02 regression check for the unified student discovery feed."""
import json
import tempfile
from pathlib import Path
import app.main as app

ROOT = Path(__file__).resolve().parent
original_db = app.DB_FILE

with tempfile.TemporaryDirectory() as tmp:
    app.DB_FILE = Path(tmp) / "unified-discovery.db"
    app.create_tables()
    app.load_fixture()
    app.r2_create_tables()
    app.r2_load_fixtures()
    app.r3_create_tables()
    app.r3_load_lifecycle_fixture()
    app.r4_create_tables()

    feed = json.loads((ROOT / "data/external_source_feed_v1.json").read_text())
    app.r4_sync_feed(feed)

    con = app.get_db()
    faculty = con.execute(
        "SELECT id FROM users WHERE email='f-alex@algomau.ca'"
    ).fetchone()
    assert faculty, "Expected verified faculty fixture is missing."
    cur = con.execute(
        """INSERT INTO industry_opportunities
        (organisation_name, contact_name, contact_email, title, description,
         areas, capacity, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'supervised')""",
        ("Local Test Organisation", "Test Contact", "contact@example.test",
         "Local Test Opportunity", "A locally supervised test opportunity.",
         "Software Engineering", "one-team-only")
    )
    con.execute(
        "INSERT INTO industry_willingness(opportunity_id, faculty_user_id) VALUES (?, ?)",
        (cur.lastrowid, faculty["id"])
    )
    con.commit()
    con.close()

    result = app.r4_unified_discovery(None)
    records = result["opportunities"]
    local = next((r for r in records if r["title"] == "Local Test Opportunity"), None)
    external = next((r for r in records if r["record_type"] == "external"), None)

    assert local is not None, "Local opportunity missing from unified discovery."
    assert external is not None, "External opportunity missing from unified discovery."
    assert local["record_type"] == "local" and local["externally_owned"] is False
    assert external["externally_owned"] is True
    assert external["source_label"], "External source attribution is required."

    print("R4-02 unified discovery verification PASSED")
    print("Local opportunity:", local["title"])
    print("External opportunity:", external["title"])
    print("External source:", external["source_label"])

app.DB_FILE = original_db
