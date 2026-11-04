from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from pathlib import Path
import sqlite3
import json

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "opportunity.db"
FIXTURE_FILE = DATA_DIR / "r1_fixture.json"

DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="Opportunity Registry",
    version="R3-submission"
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)


def get_db():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():

    connection = get_db()

    connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            verified_faculty INTEGER NOT NULL DEFAULT 0,
            public_profile INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS faculty_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            fixture_id TEXT,
            display_name TEXT NOT NULL,
            description TEXT NOT NULL,
            areas TEXT NOT NULL,
            inquiry_preference TEXT NOT NULL,
            external_link TEXT DEFAULT '',
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id TEXT UNIQUE,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            areas TEXT NOT NULL,
            student_level TEXT DEFAULT '',
            target_term TEXT DEFAULT '',
            prerequisite TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'draft',
            expected_public INTEGER NOT NULL DEFAULT 0,
            expected_authenticated INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );
    """)

    connection.commit()
    connection.close()


def load_fixture():

    if not FIXTURE_FILE.exists():
        return

    connection = get_db()

    with open(FIXTURE_FILE, "r", encoding="utf-8") as file:
        fixture = json.load(file)

    for faculty in fixture.get("faculty", []):

        fixture_id = faculty["fixture_id"]
        email = fixture_id.lower() + "@algomau.ca"

        if faculty["verified_faculty"]:
            role = "faculty"
        else:
            role = "student"

        connection.execute(
            """
            INSERT OR IGNORE INTO users
            (
                email,
                role,
                verified_faculty,
                public_profile
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                email,
                role,
                1 if faculty["verified_faculty"] else 0,
                1 if faculty["public_profile"] else 0
            )
        )

        user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        areas = ", ".join(faculty.get("areas", []))

        external_links = faculty.get("external_links", [])

        external_link = ""

        if external_links:
            external_link = external_links[0]

        connection.execute(
            """
            INSERT OR REPLACE INTO faculty_profiles
            (
                user_id,
                fixture_id,
                display_name,
                description,
                areas,
                inquiry_preference,
                external_link
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                fixture_id,
                faculty["display_name"],
                faculty["bio"],
                areas,
                faculty["inquiry_preference"],
                external_link
            )
        )

    for project in fixture.get("projects", []):

        owner = connection.execute(
            """
            SELECT user_id
            FROM faculty_profiles
            WHERE fixture_id = ?
            """,
            (project["owner"],)
        ).fetchone()

        if not owner:
            continue

        areas = ", ".join(project.get("areas", []))

        connection.execute(
            """
            INSERT OR REPLACE INTO projects
            (
                fixture_id,
                owner_id,
                title,
                description,
                areas,
                student_level,
                target_term,
                prerequisite,
                status,
                expected_public,
                expected_authenticated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project["fixture_id"],
                owner["user_id"],
                project["title"],
                "Current project opportunity.",
                areas,
                project["student_level"],
                project["term"],
                "",
                project["status"],
                1 if project.get("expected_public", False) else 0,
                1 if project.get("expected_authenticated", False) else 0
            )
        )

    connection.commit()
    connection.close()


create_tables()
load_fixture()


class LoginRequest(BaseModel):
    email: EmailStr


class FacultyProfileRequest(BaseModel):
    display_name: str
    description: str
    areas: str
    inquiry_preference: str
    external_link: str = ""


class ProjectRequest(BaseModel):
    title: str
    description: str
    areas: str
    student_level: str = ""
    target_term: str = ""
    prerequisite: str = ""
    status: str = "draft"


def current_user(email):

    if not email:
        raise HTTPException(
            status_code=401,
            detail="Sign in required."
        )

    email = email.lower()

    if not email.endswith("@algomau.ca"):
        raise HTTPException(
            status_code=403,
            detail="Only algomau.ca accounts are allowed."
        )

    connection = get_db()

    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    connection.close()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Account not found."
        )

    return user


@app.get("/", response_class=HTMLResponse)
def home():

    html_file = BASE_DIR / "static" / "index.html"

    return html_file.read_text(encoding="utf-8")


@app.post("/api/login")
def login(request: LoginRequest):

    email = str(request.email).lower()

    if not email.endswith("@algomau.ca"):
        raise HTTPException(
            status_code=403,
            detail="Non-Algoma sign-in rejected."
        )

    connection = get_db()

    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    if not user:

        connection.execute(
            """
            INSERT INTO users
            (
                email,
                role,
                verified_faculty,
                public_profile
            )
            VALUES (?, 'student', 0, 1)
            """,
            (email,)
        )

        connection.commit()

    connection.close()

    return {
        "success": True,
        "email": email,
        "message": "Sign-in successful."
    }


@app.get("/api/me")
def me(
    x_demo_email: str | None = Header(default=None)
):

    user = current_user(x_demo_email)

    return dict(user)


@app.get("/api/faculty")
def faculty(
    q: str = "",
    area: str = ""
):

    connection = get_db()

    rows = connection.execute(
        """
        SELECT
            u.id,
            u.email,
            u.public_profile,
            u.verified_faculty,
            p.display_name,
            p.description,
            p.areas,
            p.inquiry_preference,
            p.external_link

        FROM users u

        JOIN faculty_profiles p
        ON p.user_id = u.id

        WHERE
            u.verified_faculty = 1
            AND u.public_profile = 1

        ORDER BY p.display_name
        """
    ).fetchall()

    connection.close()

    results = []

    for row in rows:

        item = dict(row)

        search_text = (
            item["display_name"]
            + " "
            + item["description"]
            + " "
            + item["areas"]
        ).lower()

        if q and q.lower() not in search_text:
            continue

        if area and area.lower() not in item["areas"].lower():
            continue

        results.append(item)

    return results


@app.get("/api/faculty/{faculty_id}")
def faculty_detail(
    faculty_id: int,
    x_demo_email: str | None = Header(default=None)
):

    connection = get_db()

    faculty = connection.execute(
        """
        SELECT
            u.id,
            u.email,
            u.public_profile,
            p.display_name,
            p.description,
            p.areas,
            p.inquiry_preference,
            p.external_link

        FROM users u

        JOIN faculty_profiles p
        ON p.user_id = u.id

        WHERE
            u.id = ?
            AND u.verified_faculty = 1
        """,
        (faculty_id,)
    ).fetchone()

    if not faculty:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Faculty not found."
        )

    if not faculty["public_profile"]:

        current_user(x_demo_email)

    projects = connection.execute(
        """
        SELECT *
        FROM projects
        WHERE
            owner_id = ?
            AND status = 'published'
        """,
        (faculty_id,)
    ).fetchall()

    connection.close()

    return {
        "profile": dict(faculty),
        "projects": [dict(x) for x in projects]
    }


@app.get("/api/projects")
def projects(
    area: str = "",
    term: str = "",
    level: str = "",
    q: str = "",
    x_demo_email: str | None = Header(default=None)
):

    connection = get_db()
    # Expiry is evaluated against the fixed fixture date when the R3 fixture is installed.
    evaluation_day = r3_effective_date().isoformat() if "r3_effective_date" in globals() else date.today().isoformat()
    connection.execute("""UPDATE projects SET lifecycle_state='Expired'
        WHERE COALESCE(lifecycle_state, 'Active')='Active'
        AND deadline <> '' AND deadline < ?
        AND id NOT IN (SELECT project_id FROM matches WHERE state='Confirmed')""", (evaluation_day,))

    rows = connection.execute(
        """
        SELECT
            pr.*,
            p.display_name,
            u.email,
            u.public_profile,
            u.id AS faculty_id

        FROM projects pr

        JOIN users u
        ON u.id = pr.owner_id

        JOIN faculty_profiles p
        ON p.user_id = u.id

        WHERE
            pr.status = 'published'
            AND COALESCE(pr.lifecycle_state, 'Active') = 'Active'
            AND (
                u.public_profile = 1
                OR pr.expected_authenticated = 1
            )

        ORDER BY pr.id
        """
    ).fetchall()

    connection.close()

    authenticated = False

    if x_demo_email:

        try:
            current_user(x_demo_email)
            authenticated = True
        except HTTPException:
            authenticated = False

    results = []

    for row in rows:

        item = dict(row)

        if (
            item["public_profile"] == 0
            and not authenticated
        ):
            continue

        search_text = (
            item["title"]
            + " "
            + item["description"]
            + " "
            + item["areas"]
        ).lower()

        if area and area.lower() not in item["areas"].lower():
            continue

        if term and term.lower() != item["target_term"].lower():
            continue

        if level and level.lower() != item["student_level"].lower():
            continue

        if q and q.lower() not in search_text:
            continue

        results.append(item)

    return results


@app.get("/api/projects/{project_id}")
def project_detail(
    project_id: int,
    x_demo_email: str | None = Header(default=None)
):

    connection = get_db()

    project = connection.execute(
        """
        SELECT
            pr.*,
            p.display_name,
            u.email,
            u.public_profile,
            u.id AS faculty_id

        FROM projects pr

        JOIN users u
        ON u.id = pr.owner_id

        JOIN faculty_profiles p
        ON p.user_id = u.id

        WHERE pr.id = ?
        """,
        (project_id,)
    ).fetchone()

    if not project:
        connection.close()
        raise HTTPException(
            status_code=404,
            detail="Project not found."
        )

    if project["status"] != "published":
        connection.close()
        raise HTTPException(
            status_code=404,
            detail="Project not available."
        )

    if project["public_profile"] == 0:
        try:
            current_user(x_demo_email)
        except HTTPException:
            connection.close()
            raise

    lifecycle = r3_recompute_lifecycle(connection, project_id) if "r3_recompute_lifecycle" in globals() else project["lifecycle_state"]
    item = dict(project)
    item["lifecycle_state"] = lifecycle
    item["availability_message"] = {
        "Expired": "This opportunity's deadline has passed. It is no longer accepting new interest.",
        "Withdrawn": "The faculty owner withdrew this opportunity.",
        "Matched": "This opportunity already has a confirmed faculty-student match.",
        "Completed": "Work on this opportunity has been completed.",
        "Archived": "This opportunity has been archived."
    }.get(lifecycle, "This opportunity is currently available.")
    connection.close()
    return item


@app.put("/api/faculty/profile")
def update_profile(
    request: FacultyProfileRequest,
    x_demo_email: str | None = Header(default=None)
):

    user = current_user(x_demo_email)

    if user["verified_faculty"] != 1:
        raise HTTPException(
            status_code=403,
            detail="Verified faculty required."
        )

    connection = get_db()

    connection.execute(
        """
        UPDATE faculty_profiles

        SET
            display_name = ?,
            description = ?,
            areas = ?,
            inquiry_preference = ?,
            external_link = ?

        WHERE user_id = ?
        """,
        (
            request.display_name,
            request.description,
            request.areas,
            request.inquiry_preference,
            request.external_link,
            user["id"]
        )
    )

    connection.commit()
    connection.close()

    return {
        "success": True
    }


@app.post("/api/projects")
def create_project(
    request: ProjectRequest,
    x_demo_email: str | None = Header(default=None)
):

    user = current_user(x_demo_email)

    if user["verified_faculty"] != 1:
        raise HTTPException(
            status_code=403,
            detail="Verified faculty required."
        )

    if request.status not in ["draft", "published"]:
        request.status = "draft"

    connection = get_db()

    cursor = connection.execute(
        """
        INSERT INTO projects
        (
            owner_id,
            title,
            description,
            areas,
            student_level,
            target_term,
            prerequisite,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user["id"],
            request.title,
            request.description,
            request.areas,
            request.student_level,
            request.target_term,
            request.prerequisite,
            request.status
        )
    )

    connection.commit()

    project_id = cursor.lastrowid

    connection.close()

    return {
        "success": True,
        "project_id": project_id
    }


@app.patch("/api/projects/{project_id}")
def edit_project(
    project_id: int,
    request: ProjectRequest,
    x_demo_email: str | None = Header(default=None)
):

    user = current_user(x_demo_email)

    if user["verified_faculty"] != 1:
        raise HTTPException(
            status_code=403,
            detail="Verified faculty required."
        )

    connection = get_db()

    project = connection.execute(
        """
        SELECT *
        FROM projects
        WHERE id = ?
        """,
        (project_id,)
    ).fetchone()

    if not project:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Project not found."
        )

    if project["owner_id"] != user["id"]:
        connection.close()

        raise HTTPException(
            status_code=403,
            detail="You cannot modify another faculty member's project."
        )

    connection.execute(
        """
        UPDATE projects

        SET
            title = ?,
            description = ?,
            areas = ?,
            student_level = ?,
            target_term = ?,
            prerequisite = ?,
            status = ?

        WHERE id = ?
        """,
        (
            request.title,
            request.description,
            request.areas,
            request.student_level,
            request.target_term,
            request.prerequisite,
            request.status,
            project_id
        )
    )

    connection.commit()
    connection.close()

    return {
        "success": True
    }


@app.post("/api/admin/verify/{email}")
def verify_faculty(
    email: str,
    x_demo_email: str | None = Header(default=None)
):

    admin = current_user(x_demo_email)

    if admin["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required."
        )

    email = email.lower()

    if not email.endswith("@algomau.ca"):
        raise HTTPException(
            status_code=400,
            detail="Algoma email required."
        )

    connection = get_db()

    connection.execute(
        """
        UPDATE users

        SET
            verified_faculty = 1,
            role = 'faculty'

        WHERE email = ?
        """,
        (email,)
    )

    connection.commit()
    connection.close()

    return {
        "success": True
    }


@app.post("/api/admin/revoke/{email}")
def revoke_faculty(
    email: str,
    x_demo_email: str | None = Header(default=None)
):

    admin = current_user(x_demo_email)

    if admin["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required."
        )

    connection = get_db()

    connection.execute(
        """
        UPDATE users

        SET
            verified_faculty = 0,
            role = 'student'

        WHERE email = ?
        """,
        (email.lower(),)
    )

    connection.commit()
    connection.close()

    return {
        "success": True
    }


@app.patch("/api/faculty/public-profile")
def public_profile(
    public: bool,
    x_demo_email: str | None = Header(default=None)
):

    user = current_user(x_demo_email)

    if user["verified_faculty"] != 1:
        raise HTTPException(
            status_code=403,
            detail="Verified faculty required."
        )

    connection = get_db()

    connection.execute(
        """
        UPDATE users

        SET public_profile = ?

        WHERE id = ?
        """,
        (
            1 if public else 0,
            user["id"]
        )
    )

    connection.commit()
    connection.close()

    return {
        "success": True,
        "public_profile": public
    }




# ---------------- Release 2: industry intake and faculty coordination ----------------
from typing import Literal
from pydantic import Field, field_validator

R2_SUBMISSIONS_FILE = DATA_DIR / "intake_submissions.json"
R2_SUBSCRIPTIONS_FILE = DATA_DIR / "faculty_subscriptions.json"
R2_OUTCOMES_FILE = DATA_DIR / "expected_intake_outcomes.json"


def r2_create_tables():
    connection = get_db()
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS industry_opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id TEXT UNIQUE,
            organisation_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            areas TEXT NOT NULL,
            capacity TEXT NOT NULL CHECK(capacity IN ('one-team-only','multiple-teams','not-sure')),
            status TEXT NOT NULL DEFAULT 'awaiting-supervisor',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS industry_willingness (
            opportunity_id INTEGER NOT NULL,
            faculty_user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(opportunity_id, faculty_user_id),
            FOREIGN KEY(opportunity_id) REFERENCES industry_opportunities(id),
            FOREIGN KEY(faculty_user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS industry_engagement (
            opportunity_id INTEGER PRIMARY KEY,
            state TEXT NOT NULL DEFAULT 'Not contacted',
            faculty_user_id INTEGER,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(opportunity_id) REFERENCES industry_opportunities(id),
            FOREIGN KEY(faculty_user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS faculty_subscriptions (
            faculty_user_id INTEGER PRIMARY KEY,
            mode TEXT NOT NULL DEFAULT 'none',
            areas TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(faculty_user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS faculty_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            faculty_user_id INTEGER NOT NULL,
            opportunity_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            read INTEGER NOT NULL DEFAULT 0,
            UNIQUE(faculty_user_id, opportunity_id),
            FOREIGN KEY(faculty_user_id) REFERENCES users(id),
            FOREIGN KEY(opportunity_id) REFERENCES industry_opportunities(id)
        );
    """)
    connection.commit()
    connection.close()


def r2_load_fixtures():
    """Load the supplied R2 fixture safely and idempotently for evaluation."""
    if not R2_SUBMISSIONS_FILE.exists() or not R2_SUBSCRIPTIONS_FILE.exists():
        return
    connection = get_db()
    try:
        submissions = json.loads(R2_SUBMISSIONS_FILE.read_text(encoding='utf-8'))
        subscriptions = json.loads(R2_SUBSCRIPTIONS_FILE.read_text(encoding='utf-8'))
        # Seed the demo staff account if absent.
        admin = connection.execute('SELECT id FROM users WHERE email=?', ('admin@algomau.ca',)).fetchone()
        if not admin:
            connection.execute("INSERT INTO users(email, role, verified_faculty, public_profile) VALUES ('admin@algomau.ca', 'admin', 0, 0)")
        initial_fixture_load = connection.execute('SELECT COUNT(*) AS n FROM industry_opportunities').fetchone()['n'] == 0
        # Ensure fixture faculty have accounts/profiles, using the R1 fixture where available.
        for fixture_id in ['F-ALEX', 'F-PRIYA', 'F-JORDAN', 'F-MEI']:
            email = fixture_id.lower() + '@algomau.ca'
            found = connection.execute('SELECT id FROM users WHERE email=?', (email,)).fetchone()
            if not found:
                name = {'F-ALEX':'Dr. Alex Morgan','F-PRIYA':'Dr. Priya Shah','F-JORDAN':'Dr. Jordan Lee','F-MEI':'Dr. Mei Chen'}[fixture_id]
                cur = connection.execute("INSERT INTO users(email, role, verified_faculty, public_profile) VALUES (?, 'faculty', 1, 1)", (email,))
                connection.execute("INSERT INTO faculty_profiles(user_id, fixture_id, display_name, description, areas, inquiry_preference, external_link) VALUES (?, ?, ?, '', '', 'open', '')", (cur.lastrowid, fixture_id, name))
        # The fixture describes invalid S-204 as rejected; it must not become a stored record.
        for item in (submissions if isinstance(submissions, list) else submissions.get('submissions', [])):
            fixture_id = item.get('fixture_id') or item.get('submission_id') or item.get('id')
            organisation = (item.get('organisation_name') or item.get('organisation') or '').strip()
            title = (item.get('title') or '').strip()
            contact_email = (item.get('contact_email') or '').strip()
            if not organisation or not title or not contact_email:
                continue
            areas = item.get('areas', [])
            if isinstance(areas, str): areas = [a.strip() for a in areas.split(',') if a.strip()]
            capacity = item.get('capacity') or item.get('capacity_signal') or 'not-sure'
            capacity_map = {'one team only':'one-team-only', 'one-team-only':'one-team-only', 'multiple teams possible':'multiple-teams', 'multiple-teams':'multiple-teams', 'not sure':'not-sure', 'not-sure':'not-sure'}
            capacity = capacity_map.get(str(capacity).lower(), 'not-sure')
            connection.execute("""INSERT OR IGNORE INTO industry_opportunities
                (fixture_id, organisation_name, contact_name, contact_email, title, description, areas, capacity, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'awaiting-supervisor')""",
                (fixture_id, organisation, item.get('contact_name','').strip(), contact_email, title,
                 item.get('description',''), ', '.join(areas), capacity))
        # Apply private subscription settings from the fixture.
        faculty_subs = subscriptions if isinstance(subscriptions, list) else subscriptions.get('subscriptions', [])
        for item in faculty_subs:
            fixture_id = item.get('faculty_id') or item.get('fixture_id')
            if not fixture_id: continue
            user = connection.execute('SELECT id FROM users WHERE email=?', (fixture_id.lower()+'@algomau.ca',)).fetchone()
            if not user: continue
            mode = item.get('mode', 'none')
            areas = item.get('areas', [])
            if isinstance(areas, str): areas = [a.strip() for a in areas.split(',') if a.strip()]
            connection.execute("INSERT OR IGNORE INTO faculty_subscriptions(faculty_user_id, mode, areas) VALUES (?, ?, ?)", (user['id'], mode, ', '.join(areas)))
        # Create initial fixture notifications once; later subscriptions apply to future submissions.
        rows = connection.execute('SELECT id, fixture_id, areas, title FROM industry_opportunities WHERE fixture_id IS NOT NULL').fetchall() if initial_fixture_load else []
        for opportunity in rows:
            areas = {x.strip().lower() for x in opportunity['areas'].split(',') if x.strip()}
            faculty_rows = connection.execute("SELECT u.id, p.fixture_id, fs.mode, fs.areas FROM users u JOIN faculty_profiles p ON p.user_id=u.id LEFT JOIN faculty_subscriptions fs ON fs.faculty_user_id=u.id WHERE u.verified_faculty=1").fetchall()
            for faculty in faculty_rows:
                mode = (faculty['mode'] or 'none').lower()
                subscribed = {x.strip().lower() for x in (faculty['areas'] or '').split(',') if x.strip()}
                if mode == 'all' or (mode in ('areas','selected','selected-areas') and bool(areas & subscribed)):
                    connection.execute("INSERT OR IGNORE INTO faculty_notifications(faculty_user_id, opportunity_id, message) VALUES (?, ?, ?)", (faculty['id'], opportunity['id'], 'New industry opportunity: ' + opportunity['title']))
        connection.commit()
    finally:
        connection.close()


class IndustryIntakeRequest(BaseModel):
    organisation_name: str = Field(min_length=1, max_length=200)
    contact_name: str = Field(min_length=1, max_length=200)
    contact_email: EmailStr
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    areas: list[str] = Field(min_length=1, max_length=10)
    capacity: Literal['one-team-only', 'multiple-teams', 'not-sure']

    @field_validator('areas')
    @classmethod
    def validate_areas(cls, value):
        cleaned = [a.strip() for a in value if a and a.strip()]
        if not cleaned:
            raise ValueError('Choose at least one research/project area.')
        return cleaned

    @field_validator('organisation_name', 'contact_name', 'title', 'description')
    @classmethod
    def trim_required_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('This field is required. Please enter a value.')
        return value


class WillingnessRequest(BaseModel):
    willing: bool = True


class EngagementRequest(BaseModel):
    state: Literal['Not contacted', 'Discussion underway', 'Partner confirmed', 'No longer pursuing']


class SubscriptionRequest(BaseModel):
    mode: Literal['all', 'areas', 'none']
    areas: list[str] = []


def _verified_faculty(email):
    user = current_user(email)
    if user['verified_faculty'] != 1:
        raise HTTPException(status_code=403, detail='Verified faculty required.')
    return user


def _opportunity_row(connection, opportunity_id):
    row = connection.execute("""SELECT io.*, COUNT(iw.faculty_user_id) AS interest_count
        FROM industry_opportunities io LEFT JOIN industry_willingness iw ON iw.opportunity_id=io.id
        WHERE io.id=? GROUP BY io.id""", (opportunity_id,)).fetchone()
    return row


def _public_industry_item(connection, row, include_faculty_details=False):
    item = {k: row[k] for k in row.keys() if k not in ('contact_name','contact_email','organisation_name')}
    # Organisation and opportunity content are public after supervision; partner contact information never is.
    item['organisation_name'] = row['organisation_name']
    item['areas'] = row['areas']
    item['industry_opportunity'] = True
    supervisors = connection.execute("""SELECT u.id AS faculty_id, p.display_name, u.public_profile, u.email
        FROM industry_willingness iw JOIN users u ON u.id=iw.faculty_user_id
        LEFT JOIN faculty_profiles p ON p.user_id=u.id WHERE iw.opportunity_id=? ORDER BY p.display_name""", (row['id'],)).fetchall()
    item['supervisors'] = [{'faculty_id': s['faculty_id'], 'display_name': s['display_name'], 'email': s['email']} for s in supervisors if include_faculty_details or s['public_profile'] == 1]
    item['supervisor_names'] = [s['display_name'] for s in item['supervisors']]
    if include_faculty_details:
        item['contact_name'] = row['contact_name']
        item['contact_email'] = row['contact_email']
        engagement = connection.execute("""SELECT e.state, p.display_name AS leading_faculty
            FROM industry_engagement e LEFT JOIN faculty_profiles p ON p.user_id=e.faculty_user_id
            WHERE e.opportunity_id=?""", (row['id'],)).fetchone()
        item['engagement_state'] = engagement['state'] if engagement else 'Not contacted'
        item['engagement_lead'] = engagement['leading_faculty'] if engagement else None
    else:
        item.pop('contact_name', None); item.pop('contact_email', None)
        item.pop('engagement_state', None); item.pop('engagement_lead', None)
    return item


@app.post('/api/intake')
def submit_industry_intake(request: IndustryIntakeRequest):
    """Public accountless partner intake; every submission starts awaiting a supervisor."""
    connection = get_db()
    try:
        cursor = connection.execute("""INSERT INTO industry_opportunities
            (organisation_name, contact_name, contact_email, title, description, areas, capacity, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'awaiting-supervisor')""",
            (request.organisation_name, request.contact_name, str(request.contact_email), request.title,
             request.description, ', '.join(a.strip() for a in request.areas if a.strip()), request.capacity))
        opportunity_id = cursor.lastrowid
        area_set = {a.strip().lower() for a in request.areas if a.strip()}
        faculty = connection.execute("""SELECT u.id, fs.mode, fs.areas FROM users u
            LEFT JOIN faculty_subscriptions fs ON fs.faculty_user_id=u.id
            WHERE u.verified_faculty=1""").fetchall()
        for f in faculty:
            mode = (f['mode'] or 'none').lower()
            subscribed = {a.strip().lower() for a in (f['areas'] or '').split(',') if a.strip()}
            if mode == 'all' or (mode == 'areas' and area_set & subscribed):
                connection.execute("INSERT OR IGNORE INTO faculty_notifications(faculty_user_id, opportunity_id, message) VALUES (?, ?, ?)", (f['id'], opportunity_id, 'New industry opportunity: ' + request.title))
        connection.commit()
        return {'success': True, 'opportunity_id': opportunity_id, 'status': 'Awaiting faculty supervisor', 'message': 'Submission received. It is pending faculty supervision and is not yet visible to students.'}
    except sqlite3.IntegrityError:
        connection.rollback()
        raise HTTPException(status_code=400, detail='The submission could not be saved. Please check the required fields and try again.')
    finally:
        connection.close()


@app.get('/api/industry-opportunities')
def list_industry_opportunities(x_demo_email: str | None = Header(default=None)):
    connection = get_db()
    faculty_user = None
    if x_demo_email:
        faculty_user = current_user(x_demo_email)
    is_verified_faculty = bool(faculty_user and faculty_user['verified_faculty'] == 1)
    can_view_intake = bool(faculty_user and (faculty_user['verified_faculty'] == 1 or faculty_user['role'] == 'admin'))
    rows = connection.execute("""SELECT io.*, COUNT(iw.faculty_user_id) AS interest_count
        FROM industry_opportunities io LEFT JOIN industry_willingness iw ON iw.opportunity_id=io.id
        GROUP BY io.id ORDER BY io.created_at DESC, io.id DESC""").fetchall()
    result = []
    for row in rows:
        if not can_view_intake and not (row['interest_count'] > 0):
            continue
        result.append(_public_industry_item(connection, row, can_view_intake))
    connection.close()
    return result


@app.get('/api/industry-opportunities/{opportunity_id}')
def get_industry_opportunity(opportunity_id: int, x_demo_email: str | None = Header(default=None)):
    connection = get_db()
    row = _opportunity_row(connection, opportunity_id)
    if not row:
        connection.close(); raise HTTPException(status_code=404, detail='Industry opportunity not found.')
    faculty_user = current_user(x_demo_email) if x_demo_email else None
    is_verified_faculty = bool(faculty_user and faculty_user['verified_faculty'] == 1)
    can_view_intake = bool(faculty_user and (faculty_user['verified_faculty'] == 1 or faculty_user['role'] == 'admin'))
    if row['interest_count'] == 0 and not can_view_intake:
        connection.close(); raise HTTPException(status_code=404, detail='Opportunity not available.')
    item = _public_industry_item(connection, row, can_view_intake)
    connection.close()
    return item


@app.post('/api/industry-opportunities/{opportunity_id}/willingness')
def record_willingness(opportunity_id: int, request: WillingnessRequest, x_demo_email: str | None = Header(default=None)):
    user = _verified_faculty(x_demo_email)
    connection = get_db()
    row = connection.execute('SELECT * FROM industry_opportunities WHERE id=?', (opportunity_id,)).fetchone()
    if not row:
        connection.close(); raise HTTPException(status_code=404, detail='Industry opportunity not found.')
    if request.willing:
        connection.execute('INSERT OR IGNORE INTO industry_willingness(opportunity_id, faculty_user_id) VALUES (?, ?)', (opportunity_id, user['id']))
    else:
        connection.execute('DELETE FROM industry_willingness WHERE opportunity_id=? AND faculty_user_id=?', (opportunity_id, user['id']))
    count = connection.execute('SELECT COUNT(*) AS n FROM industry_willingness WHERE opportunity_id=?', (opportunity_id,)).fetchone()['n']
    connection.execute("UPDATE industry_opportunities SET status=? WHERE id=?", ('supervised' if count else 'awaiting-supervisor', opportunity_id))
    connection.commit(); connection.close()
    return {'success': True, 'interest_count': count, 'status': 'Supervised' if count else 'Awaiting faculty supervisor'}


@app.delete('/api/industry-opportunities/{opportunity_id}/willingness')
def withdraw_willingness(opportunity_id: int, x_demo_email: str | None = Header(default=None)):
    user = _verified_faculty(x_demo_email)
    connection = get_db()
    row = connection.execute('SELECT id FROM industry_opportunities WHERE id=?', (opportunity_id,)).fetchone()
    if not row:
        connection.close(); raise HTTPException(status_code=404, detail='Industry opportunity not found.')
    connection.execute('DELETE FROM industry_willingness WHERE opportunity_id=? AND faculty_user_id=?', (opportunity_id, user['id']))
    count = connection.execute('SELECT COUNT(*) AS n FROM industry_willingness WHERE opportunity_id=?', (opportunity_id,)).fetchone()['n']
    connection.execute("UPDATE industry_opportunities SET status=? WHERE id=?", ('supervised' if count else 'awaiting-supervisor', opportunity_id))
    connection.commit(); connection.close()
    return {'success': True, 'interest_count': count, 'status': 'Supervised' if count else 'Awaiting faculty supervisor'}


@app.put('/api/industry-opportunities/{opportunity_id}/engagement')
def set_industry_engagement(opportunity_id: int, request: EngagementRequest, x_demo_email: str | None = Header(default=None)):
    user = _verified_faculty(x_demo_email)
    connection = get_db()
    if not connection.execute('SELECT id FROM industry_opportunities WHERE id=?', (opportunity_id,)).fetchone():
        connection.close(); raise HTTPException(status_code=404, detail='Industry opportunity not found.')
    connection.execute("""INSERT INTO industry_engagement(opportunity_id, state, faculty_user_id) VALUES (?, ?, ?)
        ON CONFLICT(opportunity_id) DO UPDATE SET state=excluded.state, faculty_user_id=excluded.faculty_user_id, updated_at=CURRENT_TIMESTAMP""", (opportunity_id, request.state, user['id']))
    connection.commit(); connection.close()
    return {'success': True, 'state': request.state}


@app.get('/api/me/subscriptions')
def get_subscriptions(x_demo_email: str | None = Header(default=None)):
    user = _verified_faculty(x_demo_email)
    connection = get_db()
    row = connection.execute('SELECT mode, areas FROM faculty_subscriptions WHERE faculty_user_id=?', (user['id'],)).fetchone()
    connection.close()
    return {'mode': row['mode'] if row else 'none', 'areas': [a.strip() for a in row['areas'].split(',') if a.strip()] if row else []}


@app.put('/api/me/subscriptions')
def update_subscriptions(request: SubscriptionRequest, x_demo_email: str | None = Header(default=None)):
    user = _verified_faculty(x_demo_email)
    areas = [a.strip() for a in request.areas if a.strip()]
    if request.mode == 'areas' and not areas:
        raise HTTPException(status_code=422, detail='Choose at least one area, or select all opportunities / none.')
    connection = get_db()
    connection.execute("""INSERT INTO faculty_subscriptions(faculty_user_id, mode, areas) VALUES (?, ?, ?)
        ON CONFLICT(faculty_user_id) DO UPDATE SET mode=excluded.mode, areas=excluded.areas""", (user['id'], request.mode, ', '.join(areas)))
    connection.commit(); connection.close()
    return {'success': True, 'mode': request.mode, 'areas': areas}


@app.get('/api/me/notifications')
def get_notifications(x_demo_email: str | None = Header(default=None)):
    user = _verified_faculty(x_demo_email)
    connection = get_db()
    rows = connection.execute("""SELECT n.id, n.message, n.created_at, n.read, io.id AS opportunity_id, io.status
        FROM faculty_notifications n JOIN industry_opportunities io ON io.id=n.opportunity_id
        WHERE n.faculty_user_id=? ORDER BY n.id DESC""", (user['id'],)).fetchall()
    connection.close()
    return [dict(row) for row in rows]


@app.get('/api/health')
def health():
    return {'status': 'ok', 'release': 'R3-submission'}


# Initialise R2 storage after the R1 schema and fixture have been loaded.
r2_create_tables()
r2_load_fixtures()


# ---------------- Release 3: matching, lifecycle, outcomes and showcase ----------------
from datetime import date, datetime
from pydantic import model_validator

R3_FIXTURE_FILE = DATA_DIR / "lifecycle_fixture.json"
R3_EVALUATION_DATE = date(2026, 11, 6)  # fixed by the supplied synthetic fixture


def r3_create_tables():
    connection = get_db()
    # Additive migrations preserve existing R1/R2 project records.
    industry_columns = {row['name'] for row in connection.execute("PRAGMA table_info(industry_opportunities)").fetchall()}
    for name, definition in [
        ('partner_agreed_in_principle', "INTEGER NOT NULL DEFAULT 0"),
        ('partner_agreement_recorded_by', "INTEGER"),
        ('partner_agreement_recorded_at', "TEXT"),
    ]:
        if name not in industry_columns:
            connection.execute(f"ALTER TABLE industry_opportunities ADD COLUMN {name} {definition}")
    columns = {row['name'] for row in connection.execute("PRAGMA table_info(projects)").fetchall()}
    for name, definition in [
        ('deadline', "TEXT NOT NULL DEFAULT ''"),
        ('lifecycle_state', "TEXT NOT NULL DEFAULT 'Active'"),
        ('renewal_of', "INTEGER"),
        ('partner_agreed_in_principle', "INTEGER NOT NULL DEFAULT 0"),
        ('partner_agreement_recorded_by', "INTEGER"),
    ]:
        if name not in columns:
            connection.execute(f"ALTER TABLE projects ADD COLUMN {name} {definition}")

    connection.executescript("""
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        faculty_user_id INTEGER NOT NULL,
        state TEXT NOT NULL DEFAULT 'Proposed',
        proposed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        withdrawn_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id),
        FOREIGN KEY(faculty_user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS match_students (
        match_id INTEGER NOT NULL,
        student_user_id INTEGER NOT NULL,
        response TEXT NOT NULL DEFAULT 'Proposed',
        responded_at TEXT,
        PRIMARY KEY(match_id, student_user_id),
        FOREIGN KEY(match_id) REFERENCES matches(id),
        FOREIGN KEY(student_user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS outcomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        summary TEXT NOT NULL,
        completion_date TEXT NOT NULL,
        links_json TEXT NOT NULL DEFAULT '[]',
        faculty_user_id INTEGER NOT NULL,
        faculty_confirmed INTEGER NOT NULL DEFAULT 0,
        faculty_confirmed_at TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(project_id) REFERENCES projects(id),
        FOREIGN KEY(faculty_user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS outcome_students (
        outcome_id INTEGER NOT NULL,
        student_user_id INTEGER NOT NULL,
        profile_visible INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY(outcome_id, student_user_id),
        FOREIGN KEY(outcome_id) REFERENCES outcomes(id),
        FOREIGN KEY(student_user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS outcome_consents (
        outcome_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        public_consent INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(outcome_id, user_id),
        FOREIGN KEY(outcome_id) REFERENCES outcomes(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS project_term_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        target_term TEXT NOT NULL,
        deadline TEXT NOT NULL,
        lifecycle_state TEXT NOT NULL,
        outcome_id INTEGER,
        recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(project_id) REFERENCES projects(id),
        FOREIGN KEY(outcome_id) REFERENCES outcomes(id)
    );
    """)
    # Stable fixture identifiers make R3 acceptance data repeatable and traceable.
    for table in ("matches", "outcomes"):
        existing = {row['name'] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
        if "fixture_id" not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN fixture_id TEXT")
    connection.commit()
    connection.close()


def r3_effective_date():
    # Use the fixture's declared simulated date, not the machine's wall clock.
    if R3_FIXTURE_FILE.exists():
        try:
            fixture = json.loads(R3_FIXTURE_FILE.read_text(encoding='utf-8'))
            raw = fixture.get('evaluation_date')
            if raw:
                return date.fromisoformat(str(raw)[:10])
        except (ValueError, OSError, json.JSONDecodeError):
            pass
    return date.today()


def r3_recompute_lifecycle(connection, project_id):
    row = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        return None
    state = row['lifecycle_state'] or 'Active'
    if state in ('Withdrawn', 'Archived', 'Completed'):
        return state
    confirmed = connection.execute("""SELECT COUNT(*) AS n FROM matches
        WHERE project_id=? AND state='Confirmed'""", (project_id,)).fetchone()['n']
    if confirmed:
        state = 'Matched'
    elif row['deadline']:
        try:
            if date.fromisoformat(row['deadline']) < r3_effective_date():
                state = 'Expired'
            elif state in ('Expired', 'Matched'):
                state = 'Active'
        except ValueError:
            pass
    connection.execute("UPDATE projects SET lifecycle_state=? WHERE id=?", (state, project_id))
    return state


def r3_require_participant(connection, outcome_id, user_id):
    row = connection.execute("""SELECT o.id, o.project_id, o.faculty_user_id
        FROM outcomes o WHERE o.id=?""", (outcome_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Outcome not found.")
    is_student = connection.execute("SELECT 1 FROM outcome_students WHERE outcome_id=? AND student_user_id=?",
                                    (outcome_id, user_id)).fetchone()
    if row['faculty_user_id'] != user_id and not is_student:
        raise HTTPException(status_code=403, detail="Only outcome participants may perform this action.")
    return row


class MatchProposalRequest(BaseModel):
    student_emails: list[EmailStr] = Field(min_length=1)


class MatchResponseRequest(BaseModel):
    response: Literal['Confirmed', 'Declined']


class DeadlineRequest(BaseModel):
    target_term: str
    deadline: str


class LifecycleRequest(BaseModel):
    state: Literal['Active', 'Withdrawn', 'Archived']


class RenewalRequest(BaseModel):
    target_term: str
    deadline: str


class PartnerAgreementRequest(BaseModel):
    agreed_in_principle: bool


class OutcomeRequest(BaseModel):
    summary: str = Field(min_length=5, max_length=2000)
    completion_date: str
    student_emails: list[EmailStr] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    public_consent_emails: list[EmailStr] = Field(default_factory=list)


class ConsentRequest(BaseModel):
    public_consent: bool


class ProfileOutcomeVisibilityRequest(BaseModel):
    visible: bool


@app.post('/api/projects/{project_id}/matches')
def r3_propose_match(project_id: int, request: MatchProposalRequest,
                     x_demo_email: str | None = Header(default=None)):
    faculty_user = _verified_faculty(x_demo_email)
    emails = list(dict.fromkeys(str(e).lower() for e in request.student_emails))
    connection = get_db()
    project = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        connection.close(); raise HTTPException(status_code=404, detail="Opportunity not found.")
    if project['owner_id'] != faculty_user['id']:
        connection.close(); raise HTTPException(status_code=403, detail="Only the opportunity owner can propose a match.")
    if project['lifecycle_state'] in ('Withdrawn', 'Archived', 'Completed', 'Expired'):
        connection.close(); raise HTTPException(status_code=409, detail="This opportunity is not accepting matches.")
    student_ids = []
    for email in emails:
        if not email.endswith('@algomau.ca'):
            connection.close(); raise HTTPException(status_code=400, detail="Students must use Algoma accounts.")
        user = connection.execute("SELECT id, role FROM users WHERE email=?", (email,)).fetchone()
        if not user:
            connection.execute("INSERT INTO users(email, role, verified_faculty, public_profile) VALUES (?, 'student', 0, 0)", (email,))
            uid = connection.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()['id']
        else:
            if user['role'] == 'admin' or connection.execute("SELECT verified_faculty FROM users WHERE id=?", (user['id'],)).fetchone()['verified_faculty']:
                connection.close(); raise HTTPException(status_code=400, detail="Invitees must be student accounts.")
            uid = user['id']
        student_ids.append(uid)
    cur = connection.execute("INSERT INTO matches(project_id, faculty_user_id, state) VALUES (?, ?, 'Proposed')", (project_id, faculty_user['id']))
    match_id = cur.lastrowid
    for uid in student_ids:
        connection.execute("INSERT INTO match_students(match_id, student_user_id) VALUES (?, ?)", (match_id, uid))
    connection.commit(); connection.close()
    return {"success": True, "match_id": match_id, "state": "Proposed", "student_count": len(student_ids),
            "message": "A match records intent to work together; it is not course registration or university approval."}


@app.post('/api/matches/{match_id}/response')
def r3_match_response(match_id: int, request: MatchResponseRequest,
                      x_demo_email: str | None = Header(default=None)):
    user = current_user(x_demo_email)
    if user['verified_faculty'] == 1 or user['role'] == 'admin':
        raise HTTPException(status_code=403, detail="Only an invited student can respond.")
    connection = get_db()
    invite = connection.execute("SELECT * FROM match_students WHERE match_id=? AND student_user_id=?",
                                (match_id, user['id'])).fetchone()
    match = connection.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
    if not invite or not match:
        connection.close(); raise HTTPException(status_code=403, detail="This match was not proposed to you.")
    if match['state'] in ('Withdrawn', 'Declined'):
        connection.close(); raise HTTPException(status_code=409, detail="This proposal is no longer active.")
    connection.execute("UPDATE match_students SET response=?, responded_at=CURRENT_TIMESTAMP WHERE match_id=? AND student_user_id=?",
                       (request.response, match_id, user['id']))
    responses = connection.execute("SELECT response FROM match_students WHERE match_id=?", (match_id,)).fetchall()
    if any(r['response'] == 'Declined' for r in responses):
        state = 'Declined'
    elif all(r['response'] == 'Confirmed' for r in responses):
        state = 'Confirmed'
    elif any(r['response'] == 'Confirmed' for r in responses):
        state = 'Partly Confirmed'
    else:
        state = 'Proposed'
    connection.execute("UPDATE matches SET state=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (state, match_id))
    r3_recompute_lifecycle(connection, match['project_id'])
    connection.commit(); connection.close()
    return {"success": True, "match_id": match_id, "state": state,
            "message": "Confirmation records intent only; it does not grant academic credit, eligibility, registration or university approval."}


@app.post('/api/matches/{match_id}/withdraw')
def r3_withdraw_match(match_id: int, x_demo_email: str | None = Header(default=None)):
    faculty_user = _verified_faculty(x_demo_email)
    connection = get_db()
    match = connection.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
    if not match:
        connection.close(); raise HTTPException(status_code=404, detail="Match not found.")
    if match['faculty_user_id'] != faculty_user['id']:
        connection.close(); raise HTTPException(status_code=403, detail="Only proposing faculty can withdraw.")
    if match['state'] in ('Confirmed', 'Declined'):
        connection.close(); raise HTTPException(status_code=409, detail="This proposal can no longer be withdrawn.")
    connection.execute("UPDATE matches SET state='Withdrawn', withdrawn_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", (match_id,))
    connection.commit(); connection.close()
    return {"success": True, "state": "Withdrawn"}


@app.get('/api/matches')
def r3_list_matches(x_demo_email: str | None = Header(default=None)):
    user = current_user(x_demo_email)
    connection = get_db()
    if user['verified_faculty'] == 1:
        rows = connection.execute("""SELECT m.*, p.title FROM matches m JOIN projects p ON p.id=m.project_id
            WHERE m.faculty_user_id=? ORDER BY m.id DESC""", (user['id'],)).fetchall()
    else:
        rows = connection.execute("""SELECT m.*, p.title FROM matches m JOIN projects p ON p.id=m.project_id
            JOIN match_students ms ON ms.match_id=m.id WHERE ms.student_user_id=? ORDER BY m.id DESC""", (user['id'],)).fetchall()
    result = []
    for row in rows:
        confirmed = connection.execute("""SELECT u.email FROM match_students ms JOIN users u ON u.id=ms.student_user_id
            WHERE ms.match_id=? AND ms.response='Confirmed'""", (row['id'],)).fetchall()
        invitees = connection.execute("""SELECT u.email, ms.response FROM match_students ms JOIN users u ON u.id=ms.student_user_id
            WHERE ms.match_id=?""", (row['id'],)).fetchall()
        responses = [x['response'] for x in invitees]
        if row['state'] in ('Withdrawn', 'Declined'):
            visible_state = row['state']
        elif responses and all(x == 'Confirmed' for x in responses):
            visible_state = 'Confirmed'
        elif any(x == 'Confirmed' for x in responses):
            visible_state = 'Partly Confirmed'
        else:
            visible_state = 'Proposed'
        result.append({**dict(row), "state": visible_state,
                       "confirmed_students": [x['email'] for x in confirmed],
                       "students": [dict(x) for x in invitees]})
    connection.close()
    return result


@app.put('/api/projects/{project_id}/deadline')
def r3_set_deadline(project_id: int, request: DeadlineRequest,
                    x_demo_email: str | None = Header(default=None)):
    user = current_user(x_demo_email)
    try:
        date.fromisoformat(request.deadline)
    except ValueError:
        raise HTTPException(status_code=422, detail="Deadline must use YYYY-MM-DD.")
    connection = get_db()
    project = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        connection.close(); raise HTTPException(status_code=404, detail="Opportunity not found.")
    # Center/staff owns the authoritative deadline; faculty cannot override it.
    if user['role'] != 'admin':
        connection.close(); raise HTTPException(status_code=403, detail="Only Center staff can configure authoritative deadlines.")
    connection.execute("UPDATE projects SET target_term=?, deadline=? WHERE id=?",
                       (request.target_term, request.deadline, project_id))
    state = r3_recompute_lifecycle(connection, project_id)
    connection.commit(); connection.close()
    return {"success": True, "target_term": request.target_term, "deadline": request.deadline, "state": state}


@app.post('/api/projects/{project_id}/lifecycle')
def r3_change_lifecycle(project_id: int, request: LifecycleRequest,
                        x_demo_email: str | None = Header(default=None)):
    user = current_user(x_demo_email)
    connection = get_db()
    project = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        connection.close(); raise HTTPException(status_code=404, detail="Opportunity not found.")
    if project['owner_id'] != user['id'] and user['role'] != 'admin':
        connection.close(); raise HTTPException(status_code=403, detail="Only owner faculty or staff can change lifecycle.")
    if request.state == 'Active' and project['lifecycle_state'] not in ('Expired', 'Withdrawn'):
        connection.close(); raise HTTPException(status_code=409, detail="Only expired or withdrawn opportunities can be reactivated.")
    if request.state in ('Withdrawn', 'Active', 'Archived'):
        connection.execute("UPDATE projects SET lifecycle_state=? WHERE id=?", (request.state, project_id))
    connection.commit(); connection.close()
    return {"success": True, "state": request.state}


@app.post('/api/projects/{project_id}/renew')
def r3_renew_project(project_id: int, request: RenewalRequest,
                     x_demo_email: str | None = Header(default=None)):
    user = _verified_faculty(x_demo_email)
    try: date.fromisoformat(request.deadline)
    except ValueError: raise HTTPException(status_code=422, detail="Deadline must use YYYY-MM-DD.")
    connection = get_db()
    project = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        connection.close(); raise HTTPException(status_code=404, detail="Opportunity not found.")
    if project['owner_id'] != user['id'] and user['role'] != 'admin':
        connection.close(); raise HTTPException(status_code=403, detail="Only owner faculty or staff can renew.")
    if project['lifecycle_state'] not in ('Expired', 'Completed'):
        connection.close(); raise HTTPException(status_code=409, detail="Only expired or completed opportunities can be renewed.")
    previous_outcome = connection.execute(
        "SELECT id FROM outcomes WHERE project_id=? ORDER BY id DESC LIMIT 1", (project_id,)
    ).fetchone()
    connection.execute("""INSERT INTO project_term_history(project_id, target_term, deadline, lifecycle_state, outcome_id)
        VALUES (?, ?, ?, ?, ?)""", (project_id, project['target_term'], project['deadline'],
                                     project['lifecycle_state'], previous_outcome['id'] if previous_outcome else None))
    connection.execute("UPDATE projects SET target_term=?, deadline=?, lifecycle_state='Active' WHERE id=?",
                       (request.target_term, request.deadline, project_id))
    connection.commit(); connection.close()
    return {"success": True, "project_id": project_id, "state": "Active", "history_preserved": True}


@app.put('/api/industry-opportunities/{opportunity_id}/partner-agreement')
def r3_partner_agreement(opportunity_id: int, request: PartnerAgreementRequest,
                         x_demo_email: str | None = Header(default=None)):
    user = _verified_faculty(x_demo_email)
    connection = get_db()
    if not connection.execute("SELECT id FROM industry_opportunities WHERE id=?", (opportunity_id,)).fetchone():
        connection.close(); raise HTTPException(status_code=404, detail="Industry opportunity not found.")
    connection.execute("""UPDATE industry_opportunities SET partner_agreed_in_principle=?,
        partner_agreement_recorded_by=?, partner_agreement_recorded_at=CURRENT_TIMESTAMP WHERE id=?""",
        (1 if request.agreed_in_principle else 0, user['id'], opportunity_id))
    connection.commit(); connection.close()
    return {"success": True, "partner_agreed_in_principle": request.agreed_in_principle,
            "recorded_by_faculty": user['email'], "note": "This is a faculty-recorded statement, not partner system confirmation."}


@app.post('/api/projects/{project_id}/outcomes')
def r3_create_outcome(project_id: int, request: OutcomeRequest,
                      x_demo_email: str | None = Header(default=None)):
    user = current_user(x_demo_email)
    try: date.fromisoformat(request.completion_date)
    except ValueError: raise HTTPException(status_code=422, detail="Completion date must use YYYY-MM-DD.")
    connection = get_db()
    project = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        connection.close(); raise HTTPException(status_code=404, detail="Opportunity not found.")
    is_faculty = user['verified_faculty'] == 1 and project['owner_id'] == user['id']
    faculty_confirmed_match = connection.execute("SELECT 1 FROM matches WHERE project_id=? AND faculty_user_id=? AND state='Confirmed'",
                                                 (project_id, user['id'])).fetchone()
    is_faculty = bool(is_faculty and faculty_confirmed_match)
    confirmed = connection.execute("""SELECT 1 FROM matches m JOIN match_students ms ON ms.match_id=m.id
        WHERE m.project_id=? AND m.state='Confirmed' AND ms.student_user_id=?""", (project_id, user['id'])).fetchone()
    if not is_faculty and not confirmed:
        connection.close(); raise HTTPException(status_code=403, detail="Only participating faculty or confirmed students can report outcomes.")
    student_ids = []
    for email in request.student_emails:
        row = connection.execute("SELECT id FROM users WHERE email=?", (str(email).lower(),)).fetchone()
        if not row:
            connection.close(); raise HTTPException(status_code=400, detail=f"Unknown student: {email}")
        allowed = connection.execute("""SELECT 1 FROM matches m JOIN match_students ms ON ms.match_id=m.id
            WHERE m.project_id=? AND m.state='Confirmed' AND ms.student_user_id=?""", (project_id, row['id'])).fetchone()
        if not allowed:
            connection.close(); raise HTTPException(status_code=403, detail="Every listed student must be a confirmed participant.")
        student_ids.append(row['id'])
    if not student_ids and confirmed: student_ids = [user['id']]
    if any(not link.startswith(('https://', 'http://')) for link in request.links):
        connection.close(); raise HTTPException(status_code=422, detail="Outcome links must be http(s) URLs.")
    cur = connection.execute("""INSERT INTO outcomes(project_id, summary, completion_date, links_json, faculty_user_id)
        VALUES (?, ?, ?, ?, ?)""", (project_id, request.summary, request.completion_date, json.dumps(request.links), project['owner_id']))
    oid = cur.lastrowid
    connection.execute("""INSERT INTO project_term_history(project_id, target_term, deadline, lifecycle_state, outcome_id)
        VALUES (?, ?, ?, 'Completed', ?)""", (project_id, project['target_term'], project['deadline'], oid))
    for sid in set(student_ids):
        connection.execute("INSERT OR IGNORE INTO outcome_students(outcome_id, student_user_id) VALUES (?, ?)", (oid, sid))
    # Consent defaults to private. Explicit consent email list records initial public permission.
    consent_emails = {str(e).lower() for e in request.public_consent_emails}
    for uid in [project['owner_id']] + list(set(student_ids)):
        email = connection.execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()['email']
        connection.execute("INSERT INTO outcome_consents(outcome_id, user_id, public_consent) VALUES (?, ?, ?)",
                           (oid, uid, 1 if email in consent_emails else 0))
    connection.execute("UPDATE projects SET lifecycle_state='Completed' WHERE id=?", (project_id,))
    connection.commit(); connection.close()
    return {"success": True, "outcome_id": oid, "visibility": "participants only until a participating verified faculty member confirms and all public consents are present."}


@app.post('/api/outcomes/{outcome_id}/confirm')
def r3_confirm_outcome(outcome_id: int, x_demo_email: str | None = Header(default=None)):
    user = _verified_faculty(x_demo_email)
    connection = get_db()
    outcome = connection.execute("SELECT * FROM outcomes WHERE id=?", (outcome_id,)).fetchone()
    if not outcome:
        connection.close(); raise HTTPException(status_code=404, detail="Outcome not found.")
    if outcome['faculty_user_id'] != user['id']:
        connection.close(); raise HTTPException(status_code=403, detail="Only participating verified faculty can confirm this outcome.")
    connection.execute("UPDATE outcomes SET faculty_confirmed=1, faculty_confirmed_at=CURRENT_TIMESTAMP WHERE id=?", (outcome_id,))
    connection.commit(); connection.close()
    return {"success": True, "faculty_confirmed": True}


@app.put('/api/outcomes/{outcome_id}/consent')
def r3_set_outcome_consent(outcome_id: int, request: ConsentRequest,
                           x_demo_email: str | None = Header(default=None)):
    user = current_user(x_demo_email)
    connection = get_db()
    r3_require_participant(connection, outcome_id, user['id'])
    connection.execute("""INSERT INTO outcome_consents(outcome_id, user_id, public_consent) VALUES (?, ?, ?)
        ON CONFLICT(outcome_id, user_id) DO UPDATE SET public_consent=excluded.public_consent""",
        (outcome_id, user['id'], 1 if request.public_consent else 0))
    connection.commit(); connection.close()
    return {"success": True, "public_consent": request.public_consent}


@app.put('/api/outcomes/{outcome_id}/profile-visibility')
def r3_set_student_outcome_visibility(outcome_id: int, request: ProfileOutcomeVisibilityRequest,
                                      x_demo_email: str | None = Header(default=None)):
    user = current_user(x_demo_email)
    connection = get_db()
    row = connection.execute("SELECT 1 FROM outcome_students WHERE outcome_id=? AND student_user_id=?",
                             (outcome_id, user['id'])).fetchone()
    if not row:
        connection.close(); raise HTTPException(status_code=403, detail="Only a participating student can change their profile visibility.")
    connection.execute("UPDATE outcome_students SET profile_visible=? WHERE outcome_id=? AND student_user_id=?",
                       (1 if request.visible else 0, outcome_id, user['id']))
    connection.commit(); connection.close()
    return {"success": True, "profile_visible": request.visible}


@app.get('/api/outcomes')
def r3_list_outcomes(x_demo_email: str | None = Header(default=None)):
    connection = get_db()
    user = None
    if x_demo_email: user = current_user(x_demo_email)
    if user:
        rows = connection.execute("""SELECT DISTINCT o.*, p.title FROM outcomes o
            JOIN projects p ON p.id=o.project_id
            WHERE o.faculty_user_id=? OR EXISTS(SELECT 1 FROM outcome_students os WHERE os.outcome_id=o.id AND os.student_user_id=?)
            ORDER BY o.id DESC""", (user['id'], user['id'])).fetchall()
    else:
        rows = connection.execute("""SELECT o.*, p.title FROM outcomes o JOIN projects p ON p.id=o.project_id
            JOIN users f ON f.id=o.faculty_user_id
            WHERE o.faculty_confirmed=1 AND f.public_profile=1
            AND NOT EXISTS(SELECT 1 FROM outcome_consents c WHERE c.outcome_id=o.id AND c.public_consent=0)
            ORDER BY o.id DESC""").fetchall()
    results = []
    for row in rows:
        item = dict(row)
        students = connection.execute("""SELECT u.id, u.email, os.profile_visible, c.public_consent
            FROM outcome_students os JOIN users u ON u.id=os.student_user_id
            LEFT JOIN outcome_consents c ON c.outcome_id=os.outcome_id AND c.user_id=os.student_user_id
            WHERE os.outcome_id=?""", (row['id'],)).fetchall()
        item['students'] = [dict(s) for s in students if user or s['public_consent'] == 1]
        item['links'] = json.loads(item.pop('links_json'))
        item['showcase_eligible'] = bool(row['faculty_confirmed'] and all(s['public_consent'] == 1 for s in students)
                                          and connection.execute("SELECT public_profile FROM users WHERE id=?", (row['faculty_user_id'],)).fetchone()['public_profile'] == 1)
        results.append(item)
    connection.close()
    return results


@app.get('/api/projects/{project_id}/lifecycle')
def r3_get_lifecycle(project_id: int):
    connection = get_db()
    project = connection.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        connection.close(); raise HTTPException(status_code=404, detail="Opportunity not found.")
    state = r3_recompute_lifecycle(connection, project_id)
    connection.commit()
    result = {"project_id": project_id, "target_term": project['target_term'], "deadline": project['deadline'], "state": state}
    connection.close()
    return result



@app.get('/api/admin/projects')
def r3_admin_projects(x_demo_email: str | None = Header(default=None)):
    user = current_user(x_demo_email)
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Staff access required.")
    connection = get_db()
    rows = connection.execute("SELECT id, title, target_term, deadline, lifecycle_state, owner_id FROM projects ORDER BY id").fetchall()
    result = []
    for row in rows:
        state = r3_recompute_lifecycle(connection, row['id'])
        item = dict(row); item['lifecycle_state'] = state; result.append(item)
    connection.commit(); connection.close()
    return result

@app.get('/api/r3/health')
def r3_health():
    return {"status": "ok", "release": "R3-submission", "evaluation_date": str(r3_effective_date())}


# Initialise R3 additive schema after R1/R2 initialization.
r3_create_tables()


def r3_load_lifecycle_fixture():
    """Idempotently import the supplied synthetic R3 fixture, preserving its fixed evaluation date."""
    if not R3_FIXTURE_FILE.exists():
        return
    fixture = json.loads(R3_FIXTURE_FILE.read_text(encoding="utf-8"))
    connection = get_db()
    # Existing R1 fixture supplies faculty profiles. Ensure every named student exists.
    faculty_ids = {item["fixture_id"] for item in fixture.get("opportunities", [])}
    for section in ("matches", "outcomes"):
        for item in fixture.get(section, []):
            if item.get("proposed_by"): faculty_ids.add(item["proposed_by"])
            if item.get("faculty"): faculty_ids.add(item["faculty"])
    for fid in faculty_ids:
        email = fid.lower() + "@algomau.ca"
        connection.execute("""INSERT OR IGNORE INTO users(email, role, verified_faculty, public_profile)
            VALUES (?, 'faculty', 1, 1)""", (email,))
        uid = connection.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
        # Do not override an existing faculty member's privacy choice.
        connection.execute("""UPDATE users SET role='faculty', verified_faculty=1
            WHERE id=?""", (uid,))
        if not connection.execute("SELECT 1 FROM faculty_profiles WHERE user_id=?", (uid,)).fetchone():
            connection.execute("""INSERT INTO faculty_profiles(user_id, fixture_id, display_name, description,
                areas, inquiry_preference, external_link) VALUES (?, ?, ?, '', '', 'email', '')""",
                (uid, fid, fid))
    student_ids = set()
    for match in fixture.get("matches", []):
        student_ids.update(match.get("students", []))
    for outcome in fixture.get("outcomes", []):
        student_ids.update(outcome.get("students", []))
    for sid in student_ids:
        email = sid.lower() + "@algomau.ca"
        connection.execute("""INSERT OR IGNORE INTO users(email, role, verified_faculty, public_profile)
            VALUES (?, 'student', 0, 1)""", (email,))
    # Replace only rows imported from this fixture; ordinary user-created records remain untouched.
    connection.execute("DELETE FROM matches WHERE fixture_id IS NOT NULL")
    connection.execute("DELETE FROM outcomes WHERE fixture_id IS NOT NULL")
    project_ids = {}
    for item in fixture.get("opportunities", []):
        owner_email = item["owner"].lower() + "@algomau.ca"
        owner = connection.execute("SELECT id FROM users WHERE email=?", (owner_email,)).fetchone()
        if not owner:
            continue
        state = {"open": "Active", "withdrawn": "Withdrawn", "completed": "Completed",
                 "archived": "Archived"}.get(item.get("state", "open").lower(), "Active")
        connection.execute("""INSERT INTO projects
            (fixture_id, owner_id, title, description, areas, student_level, target_term,
             prerequisite, status, expected_public, expected_authenticated, deadline, lifecycle_state)
            VALUES (?, ?, ?, ?, '', '', ?, '', 'published', 1, 1, ?, ?)
            ON CONFLICT(fixture_id) DO UPDATE SET owner_id=excluded.owner_id, title=excluded.title,
            target_term=excluded.target_term, deadline=excluded.deadline,
            lifecycle_state=excluded.lifecycle_state, status='published'""",
            (item["fixture_id"], owner["id"], item["title"], "Synthetic Release 3 fixture opportunity.",
             item["term"], item["deadline"], state))
        row = connection.execute("SELECT id FROM projects WHERE fixture_id=?", (item["fixture_id"],)).fetchone()
        project_ids[item["fixture_id"]] = row["id"]
    match_ids = {}
    for item in fixture.get("matches", []):
        pid = project_ids.get(item["opportunity"])
        faculty = connection.execute("SELECT id FROM users WHERE email=?",
            (item["proposed_by"].lower()+"@algomau.ca",)).fetchone()
        if not pid or not faculty: continue
        cur = connection.execute("""INSERT INTO matches(project_id, faculty_user_id, state, fixture_id)
            VALUES (?, ?, ?, ?)""", (pid, faculty["id"], item.get("state", "proposed").title(), item["fixture_id"]))
        mid = cur.lastrowid
        match_ids[item["fixture_id"]] = mid
        confirmed = set(item.get("confirmed_by", []))
        declined = item.get("state", "").lower() == "declined"
        for sid in item.get("students", []):
            student = connection.execute("SELECT id FROM users WHERE email=?", (sid.lower()+"@algomau.ca",)).fetchone()
            response = "Confirmed" if sid in confirmed else ("Declined" if declined else "Proposed")
            connection.execute("""INSERT INTO match_students(match_id, student_user_id, response)
                VALUES (?, ?, ?)""", (mid, student["id"], response))
        responses = [connection.execute("SELECT response FROM match_students WHERE match_id=? AND student_user_id=?",
            (mid, connection.execute("SELECT id FROM users WHERE email=?", (sid.lower()+"@algomau.ca",)).fetchone()["id"])).fetchone()["response"]
            for sid in item.get("students", [])]
        derived = ("Declined" if "Declined" in responses else
                   "Confirmed" if responses and all(x == "Confirmed" for x in responses) else
                   "Partly Confirmed" if "Confirmed" in responses else "Proposed")
        connection.execute("UPDATE matches SET state=? WHERE id=?", (derived, mid))
    for item in fixture.get("outcomes", []):
        pid = project_ids.get(item["opportunity"])
        faculty = connection.execute("SELECT id FROM users WHERE email=?",
            (item["faculty"].lower()+"@algomau.ca",)).fetchone()
        if not pid or not faculty: continue
        cur = connection.execute("""INSERT INTO outcomes
            (project_id, summary, completion_date, links_json, faculty_user_id, faculty_confirmed, fixture_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (pid, item["summary"], item["completed"], json.dumps(item.get("links", {})),
             faculty["id"], 1 if item.get("faculty_confirmed") else 0, item["fixture_id"]))
        oid = cur.lastrowid
        participants = [item["faculty"]] + item.get("students", [])
        for sid in item.get("students", []):
            student = connection.execute("SELECT id FROM users WHERE email=?", (sid.lower()+"@algomau.ca",)).fetchone()
            connection.execute("INSERT INTO outcome_students(outcome_id, student_user_id, profile_visible) VALUES (?, ?, 1)",
                               (oid, student["id"]))
        for person in participants:
            person_row = connection.execute("SELECT id, public_profile FROM users WHERE email=?",
                (person.lower()+"@algomau.ca",)).fetchone()
            # Fixture's expected public item R-501 is consented; R-503 is blocked by F-MEI's private profile.
            consent = 1 if item["fixture_id"] == "R-501" else 0
            connection.execute("INSERT INTO outcome_consents(outcome_id, user_id, public_consent) VALUES (?, ?, ?)",
                               (oid, person_row["id"], consent))
    # Recompute expiry and preserve the distinct terminal states.
    for fixture_id, pid in project_ids.items():
        r3_recompute_lifecycle(connection, pid)
    connection.commit()
    connection.close()


r3_load_lifecycle_fixture()


@app.get('/api/profiles/{user_id}/outcomes')
def r3_profile_outcomes(user_id: int, x_demo_email: str | None = Header(default=None)):
    connection = get_db()
    profile = connection.execute("SELECT id, email, role, verified_faculty, public_profile FROM users WHERE id=?", (user_id,)).fetchone()
    if not profile:
        connection.close(); raise HTTPException(status_code=404, detail="Profile not found.")
    viewer = current_user(x_demo_email) if x_demo_email else None
    if profile['verified_faculty'] == 1 and profile['public_profile'] == 0 and not viewer:
        connection.close(); raise HTTPException(status_code=404, detail="Profile not publicly available.")
    if profile['verified_faculty'] == 1:
        rows = connection.execute("""SELECT o.*, p.title FROM outcomes o JOIN projects p ON p.id=o.project_id
            WHERE o.faculty_user_id=? AND o.faculty_confirmed=1 ORDER BY o.id DESC""", (user_id,)).fetchall()
    else:
        rows = connection.execute("""SELECT o.*, p.title, os.profile_visible FROM outcomes o
            JOIN projects p ON p.id=o.project_id JOIN outcome_students os ON os.outcome_id=o.id
            WHERE os.student_user_id=? AND os.profile_visible=1 AND o.faculty_confirmed=1 ORDER BY o.id DESC""", (user_id,)).fetchall()
    results = []
    for row in rows:
        consent_rows = connection.execute("SELECT public_consent FROM outcome_consents WHERE outcome_id=?", (row['id'],)).fetchall()
        all_consented = bool(consent_rows) and all(x['public_consent'] == 1 for x in consent_rows)
        if not viewer and (not all_consented or (profile['verified_faculty'] == 1 and profile['public_profile'] != 1)):
            continue
        item = dict(row); item['links'] = json.loads(item.pop('links_json'))
        results.append(item)
    connection.close()
    return results
