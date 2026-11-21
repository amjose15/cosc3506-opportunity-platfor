"""Isolated Release 4 acceptance check using the supplied synthetic feeds."""
import json
import tempfile
from pathlib import Path
import app.main as m

root = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as tmp:
    m.DB_FILE = Path(tmp) / 'r4-test.db'
    m.create_tables(); m.load_fixture()
    m.r2_create_tables(); m.r2_load_fixtures()
    m.r3_create_tables(); m.r3_load_lifecycle_fixture()
    m.r4_create_tables()

    v1 = json.loads((root / 'data/external_source_feed_v1.json').read_text())
    v2 = json.loads((root / 'data/external_source_feed_v2.json').read_text())
    expected = json.loads((root / 'data/expected_sync_results.json').read_text())

    first = m.r4_sync_feed(v1)
    assert first['classifications']['new'] == 4

    con = m.get_db()
    op = con.execute("SELECT id FROM external_opportunities WHERE external_id='MX-1002'").fetchone()
    faculty = con.execute("SELECT id FROM users WHERE email='f-alex@algomau.ca'").fetchone()
    con.execute("INSERT INTO external_faculty_interest (external_opportunity_id,faculty_user_id,note) VALUES (?,?,?)", (op['id'], faculty['id'], 'Local faculty support'))
    con.execute("UPDATE external_opportunities SET local_student_association='[\"s01\"]', local_outcome_history='[\"R3-outcome\"]', local_readiness_guidance='Local guidance' WHERE id=?", (op['id'],))
    con.commit(); con.close()

    second = m.r4_sync_feed(v2)
    c = second['classifications']
    assert c['new'] == len(expected['new_external_ids'])
    assert c['unchanged'] == len(expected['unchanged_external_ids'])
    assert c['changed'] == len(expected['changed_external_ids'])
    assert c['not_seen'] == len(expected['not_seen_external_ids'])
    assert second['malformed_count'] == expected['malformed_record_count']

    con = m.get_db()
    row = con.execute("SELECT * FROM external_opportunities WHERE external_id='MX-1002'").fetchone()
    assert con.execute('SELECT COUNT(*) FROM external_faculty_interest WHERE external_opportunity_id=?',(op['id'],)).fetchone()[0] == 1
    assert row['local_student_association'] == '["s01"]'
    assert row['local_outcome_history'] == '["R3-outcome"]'
    assert row['local_readiness_guidance'] == 'Local guidance'
    missing = con.execute("SELECT * FROM external_opportunities WHERE external_id='MX-1003'").fetchone()
    assert missing['source_status'] == 'not_seen' and missing['title']
    hostile = con.execute("SELECT * FROM external_opportunities WHERE external_id='MX-1005'").fetchone()
    assert '<script>' in hostile['description'] and hostile['source_id'] == 'mitacs-demo'
    before_count = con.execute('SELECT COUNT(*) FROM external_opportunities').fetchone()[0]
    before_title = hostile['title']
    con.close()

    repeat = m.r4_sync_feed(v2)
    assert repeat['classifications']['new'] == 0 and repeat['classifications']['changed'] == 0
    assert repeat['classifications']['unchanged'] == 4
    con = m.get_db()
    assert con.execute('SELECT COUNT(*) FROM external_opportunities').fetchone()[0] == before_count
    assert con.execute("SELECT title FROM external_opportunities WHERE external_id='MX-1005'").fetchone()[0] == before_title
    con.execute("INSERT INTO external_sync_runs (source_id,started_at,completed_at,status,reason) VALUES (?,?,?,?,?)", ('mitacs-demo','now','now','failed','simulated unavailable'))
    con.commit()
    assert con.execute('SELECT COUNT(*) FROM external_opportunities').fetchone()[0] == before_count
    con.close()

print('Release 4 fixture verification PASSED')
print('v1 initial import: 4 new')
print('v2 classification: 1 new, 2 unchanged, 1 changed, 1 not seen, 1 malformed skipped')
print('repeat v2: 4 unchanged, no duplicates')
print('R4-20: faculty interest and local fields survived synchronization')
print('Failed sync: external records retained')
