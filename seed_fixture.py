"""
Loads the official Moodle r1_fixture.json into the local SQLite database.

Because the official fixture was not attached when this starter was generated,
place it at data/r1_fixture.json. Inspect its top-level shape and map its fields
if necessary. This script deliberately keeps the database schema simple.
"""
import json, sqlite3
from pathlib import Path
p=Path("data/r1_fixture.json")
if not p.exists():
    print("Missing data/r1_fixture.json. Download it from Moodle first.")
    raise SystemExit(1)
data=json.loads(p.read_text())
print("Fixture loaded. Top-level type:", type(data).__name__)
print("Keys:", list(data.keys()) if isinstance(data,dict) else "list")
print("Review the fixture field names and extend this script if required.")
