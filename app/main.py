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
    version="R1-submission"
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


@app.get("/api/health")
def health():

    return {
        "status": "ok",
        "release": "R1-submission"
    }
