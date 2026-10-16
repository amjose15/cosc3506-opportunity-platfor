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
    version="R2-submission"
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

    connection.close()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found."
        )

    if project["status"] != "published":
        raise HTTPException(
            status_code=404,
            detail="Project not available."
        )

    if project["public_profile"] == 0:
        current_user(x_demo_email)

    return dict(project)


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
    return {'status': 'ok', 'release': 'R2-submission'}


# Initialise R2 storage after the R1 schema and fixture have been loaded.
r2_create_tables()
r2_load_fixtures()
