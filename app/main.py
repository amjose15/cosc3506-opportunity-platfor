from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from pathlib import Path
import sqlite3, secrets, time

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "data" / "r1.db"
DB.parent.mkdir(exist_ok=True)
STATIC = BASE / "static"

app = FastAPI(title="Opportunity Registry R1")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email TEXT UNIQUE NOT NULL,
      role TEXT NOT NULL DEFAULT 'student',
      verified_faculty INTEGER NOT NULL DEFAULT 0,
      public_profile INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS profiles(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER UNIQUE NOT NULL,
      display_name TEXT NOT NULL,
      description TEXT NOT NULL DEFAULT '',
      areas TEXT NOT NULL DEFAULT '',
      inquiry_preference TEXT NOT NULL DEFAULT 'open',
      external_link TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS projects(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      owner_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      description TEXT NOT NULL,
      areas TEXT NOT NULL DEFAULT '',
      student_level TEXT NOT NULL DEFAULT '',
      target_term TEXT NOT NULL DEFAULT '',
      prerequisite TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'draft'
    );
    """)
    # Safe demo accounts. In final deployment replace with real institutional auth.
    for email, role, vf in [
        ("student@algomau.ca","student",0),
        ("faculty@algomau.ca","faculty",1),
        ("admin@algomau.ca","admin",0),
    ]:
        con.execute("INSERT OR IGNORE INTO users(email,role,verified_faculty) VALUES(?,?,?)",(email,role,vf))
    faculty = con.execute("SELECT id FROM users WHERE email='faculty@algomau.ca'").fetchone()
    if faculty:
        con.execute("""INSERT OR IGNORE INTO profiles(user_id,display_name,description,areas,inquiry_preference)
                       VALUES(?,?,?,?,?)""",
                    (faculty["id"],"Dr. Maya Thomas",
                     "Researcher working with students on practical computing projects.",
                     "Cybersecurity, AI, Software Engineering","open"))
        if con.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"] == 0:
            con.execute("""INSERT INTO projects(owner_id,title,description,areas,student_level,target_term,prerequisite,status)
                           VALUES(?,?,?,?,?,?,?,?)""",
                        (faculty["id"],"Secure Campus Services",
                         "Explore security improvements for a small university service.",
                         "Cybersecurity, Software Engineering","Undergraduate","Fall 2026",
                         "Basic programming and security interest","published"))
    con.commit(); con.close()

init_db()

class Login(BaseModel):
    email: EmailStr

class ProfileIn(BaseModel):
    display_name: str
    description: str
    areas: str
    inquiry_preference: str = "open"
    external_link: str = ""

class ProjectIn(BaseModel):
    title: str
    description: str
    areas: str
    student_level: str = ""
    target_term: str = ""
    prerequisite: str = ""
    status: str = "draft"

def current_user(x_demo_email: str | None):
    if not x_demo_email:
        raise HTTPException(401,"Sign in required")
    email=x_demo_email.strip().lower()
    if not email.endswith("@algomau.ca"):
        raise HTTPException(403,"Only algomau.ca accounts are allowed")
    con=db(); u=con.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); con.close()
    if not u: raise HTTPException(401,"Account not found")
    return u

@app.get("/", response_class=HTMLResponse)
def home():
    return (STATIC/"index.html").read_text()

@app.post("/api/login")
def login(body: Login):
    email=str(body.email).lower()
    if email.split("@")[-1] != "algomau.ca":
        raise HTTPException(403,"Non-Algoma sign-in rejected")
    # Explicit demo/test mode. A real deployment should replace this with
    # instructor-approved magic-link/OTP delivery.
    con=db()
    u=con.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
    if not u:
        con.execute("INSERT INTO users(email,role) VALUES(?,?)",(email,"student"))
        con.commit()
    con.close()
    return {"ok":True,"test_mode":True,"message":"Test-mode sign-in accepted. Use this email as X-Demo-Email."}

@app.get("/api/me")
def me(x_demo_email: str|None = Header(default=None)):
    u=current_user(x_demo_email)
    return dict(u)

@app.get("/api/faculty")
def faculty(q: str="", area: str=""):
    con=db()
    rows=con.execute("""SELECT u.id,u.email,u.verified_faculty,u.public_profile,
                               p.display_name,p.description,p.areas,p.inquiry_preference,p.external_link
                        FROM users u JOIN profiles p ON p.user_id=u.id
                        WHERE u.verified_faculty=1 AND u.public_profile=1
                        ORDER BY p.display_name""").fetchall()
    con.close()
    out=[]
    for r in rows:
        d=dict(r)
        if q and q.lower() not in (d["display_name"]+" "+d["description"]+" "+d["areas"]).lower(): continue
        if area and area.lower() not in d["areas"].lower(): continue
        out.append(d)
    return out

@app.get("/api/faculty/{fid}")
def faculty_detail(fid:int, x_demo_email: str|None=Header(default=None)):
    con=db()
    r=con.execute("""SELECT u.id,u.email,u.public_profile,p.display_name,p.description,p.areas,
                            p.inquiry_preference,p.external_link
                     FROM users u JOIN profiles p ON p.user_id=u.id WHERE u.id=? AND u.verified_faculty=1""",(fid,)).fetchone()
    if not r: raise HTTPException(404,"Faculty not found")
    u=current_user(x_demo_email) if x_demo_email else None
    if not r["public_profile"] and not u: raise HTTPException(404,"Faculty not publicly available")
    projects=con.execute("""SELECT * FROM projects WHERE owner_id=? AND status='published'""",(fid,)).fetchall()
    con.close()
    return {"profile":dict(r),"projects":[dict(x) for x in projects]}

@app.get("/api/projects")
def projects(area:str="", term:str="", level:str="", q:str=""):
    con=db()
    rows=con.execute("""SELECT pr.*,p.display_name,u.email,u.public_profile
                        FROM projects pr JOIN users u ON u.id=pr.owner_id
                        JOIN profiles p ON p.user_id=u.id
                        WHERE pr.status='published' AND u.public_profile=1
                        ORDER BY pr.id DESC""").fetchall()
    con.close()
    out=[]
    for r in rows:
        d=dict(r); hay=(d["title"]+" "+d["description"]+" "+d["areas"]).lower()
        if area and area.lower() not in d["areas"].lower(): continue
        if term and term.lower()!=d["target_term"].lower(): continue
        if level and level.lower()!=d["student_level"].lower(): continue
        if q and q.lower() not in hay: continue
        out.append(d)
    return out

@app.get("/api/projects/{pid}")
def project_detail(pid:int, x_demo_email: str|None=Header(default=None)):
    con=db()
    r=con.execute("""SELECT pr.*,p.display_name,u.email,u.public_profile,u.id faculty_id
                     FROM projects pr JOIN users u ON u.id=pr.owner_id
                     JOIN profiles p ON p.user_id=u.id WHERE pr.id=?""",(pid,)).fetchone()
    con.close()
    if not r or r["status"]!="published": raise HTTPException(404,"Project not found")
    if not r["public_profile"]:
        current_user(x_demo_email)
    return dict(r)

@app.put("/api/faculty/profile")
def update_profile(body:ProfileIn,x_demo_email:str|None=Header(default=None)):
    u=current_user(x_demo_email)
    if u["verified_faculty"]!=1: raise HTTPException(403,"Verified faculty required")
    con=db()
    con.execute("""INSERT INTO profiles(user_id,display_name,description,areas,inquiry_preference,external_link)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name,
                   description=excluded.description,areas=excluded.areas,
                   inquiry_preference=excluded.inquiry_preference,external_link=excluded.external_link""",
                (u["id"],body.display_name,body.description,body.areas,body.inquiry_preference,body.external_link))
    con.commit(); con.close()
    return {"ok":True}

@app.post("/api/projects")
def create_project(body:ProjectIn,x_demo_email:str|None=Header(default=None)):
    u=current_user(x_demo_email)
    if u["verified_faculty"]!=1: raise HTTPException(403,"Verified faculty required")
    if body.status not in ("draft","published"): body.status="draft"
    con=db()
    cur=con.execute("""INSERT INTO projects(owner_id,title,description,areas,student_level,target_term,prerequisite,status)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (u["id"],body.title,body.description,body.areas,body.student_level,body.target_term,body.prerequisite,body.status))
    con.commit(); pid=cur.lastrowid; con.close()
    return {"id":pid,"status":body.status}

@app.patch("/api/projects/{pid}")
def edit_project(pid:int, body:ProjectIn, x_demo_email:str|None=Header(default=None)):
    u=current_user(x_demo_email)
    if u["verified_faculty"]!=1: raise HTTPException(403,"Verified faculty required")
    con=db(); p=con.execute("SELECT * FROM projects WHERE id=?",(pid,)).fetchone()
    if not p: raise HTTPException(404,"Project not found")
    if p["owner_id"]!=u["id"]: raise HTTPException(403,"You do not own this project")
    con.execute("""UPDATE projects SET title=?,description=?,areas=?,student_level=?,target_term=?,prerequisite=?,status=?
                   WHERE id=?""",
                (body.title,body.description,body.areas,body.student_level,body.target_term,body.prerequisite,body.status,pid))
    con.commit(); con.close(); return {"ok":True}

@app.post("/api/admin/verify/{email}")
def verify(email:str,x_demo_email:str|None=Header(default=None)):
    u=current_user(x_demo_email)
    if u["role"]!="admin": raise HTTPException(403,"Admin required")
    if not email.endswith("@algomau.ca"): raise HTTPException(400,"Algoma email required")
    con=db(); con.execute("UPDATE users SET verified_faculty=1,role='faculty' WHERE email=?",(email,)); con.commit(); con.close()
    return {"ok":True}
