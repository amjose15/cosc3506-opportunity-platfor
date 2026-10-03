from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from pathlib import Path
import sqlite3

# --------------------------------------------------
# BASIC SETUP
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_FILE = DATA_DIR / "opportunity.db"

DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="Opportunity Registry",
    description="COSC-3506 Project 2 - Release 1",
    version="R1-submission"
)

# Serve the frontend
app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def get_db():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():

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
        display_name TEXT NOT NULL,
        description TEXT NOT NULL,
        areas TEXT NOT NULL,
        inquiry_preference TEXT NOT NULL,
        external_link TEXT DEFAULT '',
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        areas TEXT NOT NULL,
        student_level TEXT DEFAULT '',
        target_term TEXT DEFAULT '',
        prerequisite TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'draft',
        FOREIGN KEY(owner_id) REFERENCES users(id)
    );

    """)

    # --------------------------------------------------
    # DEMO USERS
    # --------------------------------------------------

    demo_users = [
        ("student@algomau.ca", "student", 0),
        ("faculty@algomau.ca", "faculty", 1),
        ("admin@algomau.ca", "admin", 0)
    ]

    for email, role, verified in demo_users:

        connection.execute(
            """
            INSERT OR IGNORE INTO users
            (email, role, verified_faculty)
            VALUES (?, ?, ?)
            """,
            (email, role, verified)
        )

    # --------------------------------------------------
    # DEMO FACULTY
    # --------------------------------------------------

    faculty = connection.execute(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        ("faculty@algomau.ca",)
    ).fetchone()

    if faculty:

        connection.execute(
            """
            INSERT OR IGNORE INTO faculty_profiles
            (
                user_id,
                display_name,
                description,
                areas,
                inquiry_preference,
                external_link
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                faculty["id"],
                "Dr. Maya Thomas",
                "Researcher working with students on practical computing projects.",
                "Cybersecurity, Software Engineering, Artificial Intelligence",
                "open",
                ""
            )
        )

        # --------------------------------------------------
        # DEMO PROJECT
        # --------------------------------------------------

        existing_project = connection.execute(
            """
            SELECT id
            FROM projects
            WHERE owner_id = ?
            """,
            (faculty["id"],)
        ).fetchone()

        if not existing_project:

            connection.execute(
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
                    faculty["id"],
                    "Secure Campus Services",
                    "Explore security improvements for a small university service.",
                    "Cybersecurity, Software Engineering",
                    "Undergraduate",
                    "Fall 2026",
                    "Basic programming and an interest in cybersecurity",
                    "published"
                )
            )

    connection.commit()
    connection.close()


initialize_database()


# --------------------------------------------------
# DATA MODELS
# --------------------------------------------------

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


# --------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------

def get_current_user(
    demo_email: str | None
):

    if not demo_email:

        raise HTTPException(
            status_code=401,
            detail="Please sign in."
        )

    email = demo_email.strip().lower()

    # R1-02
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


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home():

    html_file = BASE_DIR / "static" / "index.html"

    if not html_file.exists():

        return """
        <h1>Opportunity Registry</h1>
        <p>Frontend file not found.</p>
        """

    return html_file.read_text()


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.post("/api/login")
def login(request: LoginRequest):

    email = str(request.email).lower()

    # R1-02
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

    # New Algoma users start as students.
    if not user:

        connection.execute(
            """
            INSERT INTO users
            (email, role, verified_faculty)
            VALUES (?, ?, ?)
            """,
            (email, "student", 0)
        )

        connection.commit()

    connection.close()

    return {
        "success": True,
        "message": "Sign-in successful.",
        "email": email
    }


# --------------------------------------------------
# CURRENT USER
# --------------------------------------------------

@app.get("/api/me")
def get_me(
    x_demo_email: str | None = Header(default=None)
):

    user = get_current_user(x_demo_email)

    return dict(user)


# --------------------------------------------------
# FACULTY DISCOVERY
# --------------------------------------------------

@app.get("/api/faculty")
def get_faculty(
    q: str = "",
    area: str = ""
):

    connection = get_db()

    faculty = connection.execute(
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

    for person in faculty:

        person = dict(person)

        search_text = (
            person["display_name"]
            + " "
            + person["description"]
            + " "
            + person["areas"]
        ).lower()

        if q:

            if q.lower() not in search_text:
                continue

        if area:

            if area.lower() not in person["areas"].lower():
                continue

        results.append(person)

    return results


# --------------------------------------------------
# FACULTY DETAILS
# --------------------------------------------------

@app.get("/api/faculty/{faculty_id}")
def faculty_details(
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
            detail="Faculty member not found."
        )

    # Private faculty may only be seen by authenticated users.
    if not faculty["public_profile"]:

        get_current_user(x_demo_email)

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
        "projects": [
            dict(project)
            for project in projects
        ]
    }


# --------------------------------------------------
# PROJECT DISCOVERY
# --------------------------------------------------

@app.get("/api/projects")
def get_projects(
    area: str = "",
    term: str = "",
    level: str = "",
    q: str = ""
):

    connection = get_db()

    projects = connection.execute(
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
            AND u.public_profile = 1

        ORDER BY pr.id DESC
        """
    ).fetchall()

    connection.close()

    results = []

    for project in projects:

        project = dict(project)

        search_text = (
            project["title"]
            + " "
            + project["description"]
            + " "
            + project["areas"]
        ).lower()

        if area:

            if area.lower() not in project["areas"].lower():
                continue

        if term:

            if term.lower() != project["target_term"].lower():
                continue

        if level:

            if level.lower() != project["student_level"].lower():
                continue

        if q:

            if q.lower() not in search_text:
                continue

        results.append(project)

    return results


# --------------------------------------------------
# PROJECT DETAILS
# --------------------------------------------------

@app.get("/api/projects/{project_id}")
def project_details(
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

    # Private faculty projects require authentication.
    if not project["public_profile"]:

        get_current_user(x_demo_email)

    return dict(project)


# --------------------------------------------------
# FACULTY PROFILE UPDATE
# --------------------------------------------------

@app.put("/api/faculty/profile")
def update_faculty_profile(
    request: FacultyProfileRequest,
    x_demo_email: str | None = Header(default=None)
):

    user = get_current_user(x_demo_email)

    # Only verified faculty.
    if user["verified_faculty"] != 1:

        raise HTTPException(
            status_code=403,
            detail="Verified faculty access required."
        )

    connection = get_db()

    connection.execute(
        """
        INSERT INTO faculty_profiles
        (
            user_id,
            display_name,
            description,
            areas,
            inquiry_preference,
            external_link
        )
        VALUES (?, ?, ?, ?, ?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            display_name = excluded.display_name,
            description = excluded.description,
            areas = excluded.areas,
            inquiry_preference = excluded.inquiry_preference,
            external_link = excluded.external_link
        """,
        (
            user["id"],
            request.display_name,
            request.description,
            request.areas,
            request.inquiry_preference,
            request.external_link
        )
    )

    connection.commit()
    connection.close()

    return {
        "success": True,
        "message": "Faculty profile updated."
    }


# --------------------------------------------------
# CREATE PROJECT
# --------------------------------------------------

@app.post("/api/projects")
def create_project(
    request: ProjectRequest,
    x_demo_email: str | None = Header(default=None)
):

    user = get_current_user(x_demo_email)

    if user["verified_faculty"] != 1:

        raise HTTPException(
            status_code=403,
            detail="Verified faculty access required."
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
        "project_id": project_id,
        "status": request.status
    }


# --------------------------------------------------
# EDIT PROJECT
# --------------------------------------------------

@app.patch("/api/projects/{project_id}")
def edit_project(
    project_id: int,
    request: ProjectRequest,
    x_demo_email: str | None = Header(default=None)
):

    user = get_current_user(x_demo_email)

    if user["verified_faculty"] != 1:

        raise HTTPException(
            status_code=403,
            detail="Verified faculty access required."
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

    # R1-16
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
        "success": True,
        "message": "Project updated."
    }


# --------------------------------------------------
# ADMIN: VERIFY FACULTY
# --------------------------------------------------

@app.post("/api/admin/verify/{email}")
def verify_faculty(
    email: str,
    x_demo_email: str | None = Header(default=None)
):

    admin = get_current_user(x_demo_email)

    if admin["role"] != "admin":

        raise HTTPException(
            status_code=403,
            detail="Administrator access required."
        )

    email = email.lower()

    if not email.endswith("@algomau.ca"):

        raise HTTPException(
            status_code=400,
            detail="Only Algoma email addresses can be verified."
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
        "success": True,
        "message": "Faculty status verified."
    }


# --------------------------------------------------
# ADMIN: REVOKE FACULTY
# --------------------------------------------------

@app.post("/api/admin/revoke/{email}")
def revoke_faculty(
    email: str,
    x_demo_email: str | None = Header(default=None)
):

    admin = get_current_user(x_demo_email)

    if admin["role"] != "admin":

        raise HTTPException(
            status_code=403,
            detail="Administrator access required."
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
        "success": True,
        "message": "Faculty status revoked."
    }


# --------------------------------------------------
# CHANGE PUBLIC PROFILE
# --------------------------------------------------

@app.patch("/api/faculty/public-profile")
def change_public_profile(
    public: bool,
    x_demo_email: str | None = Header(default=None)
):

    user = get_current_user(x_demo_email)

    if user["verified_faculty"] != 1:

        raise HTTPException(
            status_code=403,
            detail="Verified faculty access required."
        )

    connection = get_db()

    connection.execute(
        """
        UPDATE users

        SET public_profile = ?

        WHERE id = ?
        """,
        (1 if public else 0, user["id"])
    )

    connection.commit()
    connection.close()

    return {
        "success": True,
        "public_profile": public
    }


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/api/health")
def health():

    return {
        "status": "ok",
        "release": "R1-submission"
    }
