"""
================================================================
 RKMS MediStock Pro — Backend API
 FastAPI + SQLAlchemy + SQLite
 ----------------------------------------------------------------
 Single-file backend covering every module of 789.html:
   Medicines, Doctors, Students, Dispense, Prescriptions,
   Daily Report, Analytics, Stock Value, Notice Board,
   Activity Log, Auth (JWT, role-based), Backup/Restore.

 RUN:
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000

 Interactive API docs (auto-generated):
   http://127.0.0.1:8000/docs

 Default logins (seeded on first run):
   admin  / admin123
   staff       / staff123   (Staff Console)
   medicalward / ward123    (Medical Ward Console)

 GOOGLE LOGIN (added):
   POST /auth/google/link — "Continue with Google" button on the DASHBOARD (top-right): registers a Google account.
   POST /auth/google      — Google sign-in, allowed ONLY for accounts registered that way.
   GET  /privacy      — privacy policy page (needed by Google Cloud Branding).

 STAFF REGISTRATION + ADMIN APPROVAL (ported from the Student Conduct app):
   POST /auth/register              — public: new staff request an account (status = pending)
   POST /auth/login                 — username OR email + password; pending/rejected accounts are refused
   GET  /auth/users                 — admin: list all users
   POST /auth/users/{id}/approve    — admin: approve (optionally set role doctor|nurse)
   POST /auth/users/{id}/reject     — admin: reject / disable
   DELETE /auth/users/{id}          — admin: remove a user
   POST /auth/users/reset           — admin: remove every user except the owner ("admin")
   POST /auth/change-password       — any logged-in user changes their own password
   Optional environment variables (set them in Render > Environment):
     GOOGLE_CLIENT_ID       — OAuth Web client ID (default is already set below)
     GOOGLE_ALLOWED_DOMAINS — e.g. "rkmshome.org"  (empty = ANY Google account)
     GOOGLE_ADMIN_EMAILS    — e.g. "me@rkmshome.org" (empty = ANY account can pick Admin)
     RKMS_PRIVACY_CONTACT   — contact email shown on the /privacy page
================================================================
"""

import os
import calendar
import io
import csv
import json
import shutil
import secrets
import urllib.parse
import urllib.request
import urllib.error
import time
from datetime import datetime, timedelta, date
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse, HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean, DateTime, Date,
    ForeignKey, Text, func
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session

from pydantic import BaseModel, ConfigDict
import bcrypt
from jose import jwt, JWTError

# ================================================================
# 1. CONFIG
# ================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "rkms_medistock.db")

# By default, uses a local SQLite file (single-laptop mode).
# To share one database across multiple laptops on a network, set the
# RKMS_DATABASE_URL environment variable to a PostgreSQL connection
# string on the central computer, e.g.:
#   postgresql://rkms_user:yourpassword@localhost:5432/rkms_medistock
# Every other laptop then just opens a browser to that computer's IP —
# they don't need Postgres, Python, or anything else installed.
DATABASE_URL = os.environ.get("RKMS_DATABASE_URL", f"sqlite:///{DB_PATH}")
# Force the psycopg2 driver explicitly. Newer SQLAlchemy versions may otherwise
# default a plain "postgresql://" URL to the psycopg (v3) dialect, which isn't
# installed here (we install psycopg2-binary via the [postgres] extra).
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

SECRET_KEY = os.environ.get("RKMS_SECRET_KEY", "rkms-medistock-change-this-secret-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days — a laptop that logged in once stays logged in (renewed on every open)

# ---- Google login settings ----
GOOGLE_CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "537417539303-r2oipsrkqcjuggbfgh4launrv0tq8g5r.apps.googleusercontent.com",
)
# Empty list = ANY Google account is allowed. Example: GOOGLE_ALLOWED_DOMAINS="rkmshome.org"
GOOGLE_ALLOWED_DOMAINS = [d.strip().lower() for d in os.environ.get("GOOGLE_ALLOWED_DOMAINS", "").split(",") if d.strip()]
# Empty list = ANY Google account may choose the Admin role. Example: GOOGLE_ADMIN_EMAILS="a@x.org,b@x.org"
GOOGLE_ADMIN_EMAILS = [e.strip().lower() for e in os.environ.get("GOOGLE_ADMIN_EMAILS", "").split(",") if e.strip()]
PRIVACY_CONTACT = os.environ.get("RKMS_PRIVACY_CONTACT", "poojidthkumar.s.2027@rkmshome.org")

# ================================================================
# 2. DATABASE SETUP
# ================================================================
_engine_kwargs = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ================================================================
# 3. MODELS  (one table per 789.html module)
# ================================================================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="nurse")  # admin | doctor | nurse
    email = Column(String, default="", index=True)          # Google email (blank for password users)
    session_id = Column(String, default="")                 # the ONE live session allowed for this account
    session_seen = Column(DateTime)                         # last heartbeat of that session
    g_name = Column(String, default="")                     # linked Google profile (shown on dashboard)
    g_picture = Column(String, default="")
    logged_out_at = Column(DateTime)                        # "log out everywhere": tokens issued before this are rejected
    name = Column(String, default="")                       # full name shown in the app
    dept = Column(String, default="")
    designation = Column(String, default="")
    contact_email = Column(String, default="", index=True)  # e-mail typed at registration (NOT verified - never used to match Google logins)
    status = Column(String, default="approved")             # pending | approved | rejected
    created_at = Column(DateTime, default=datetime.utcnow)


class Medicine(Base):
    __tablename__ = "medicines"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, default="")
    batch = Column(String, default="")
    qty = Column(Integer, default=0)
    min_alert = Column(Integer, default=10)
    price = Column(Float, default=0.0)
    expiry = Column(String, default="")   # stored as ISO date string, matches frontend <input type=date>
    dose = Column(String, default="")
    note = Column(String, default="")
    img = Column(Text, default="")        # optional base64 image, matches frontend
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    specialization = Column(String, default="")
    contact = Column(String, default="")
    days = Column(String, default="")      # e.g. "Mon, Wed, Fri" — matches frontend
    timing = Column(String, default="")    # e.g. "10am - 1pm" — matches frontend
    created_at = Column(DateTime, default=datetime.utcnow)


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    roll = Column(String, default="")
    dept = Column(String, default="")
    year = Column(String, default="")
    blood = Column(String, default="")
    bday = Column(String, default="")      # ISO date string
    phone = Column(String, default="")
    ec = Column(String, default="")        # emergency contact
    allergy = Column(String, default="")
    addr = Column(String, default="")
    img = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class DispenseRecord(Base):
    __tablename__ = "dispense_records"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False)
    doctor_name = Column(String, default="")
    qty = Column(Integer, default=1)
    sched = Column(String, default="")     # dosage schedule e.g. 1-0-1
    note = Column(String, default="")      # diagnosis / notes
    dispensed_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("Student")
    medicine = relationship("Medicine")


class Notice(Base):
    __tablename__ = "notices"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, default="")
    color = Column(String, default="yellow")
    posted_by = Column(String, default="")
    posted_at = Column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_log"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String, default="")
    action = Column(String, nullable=False)
    type = Column(String, default="success")  # success | danger | info
    timestamp = Column(DateTime, default=datetime.utcnow)


class BackupLog(Base):
    """One row per backup attempt, so anyone can check that a backup really reached Google Drive."""
    __tablename__ = "backup_log"
    id = Column(Integer, primary_key=True, index=True)
    at = Column(DateTime, default=datetime.utcnow)
    username = Column(String, default="")
    ok = Column(Boolean, default=False)
    verified = Column(Boolean, default=False)      # server re-read the file from Drive and the size matched
    name = Column(String, default="")
    size = Column(Integer, default=0)
    summary = Column(String, default="")           # e.g. "24 medicines, 130 students, 4 doctors"
    link = Column(String, default="")
    error = Column(String, default="")
    file_id = Column(String, default="")           # Google Drive file id, used by View / Download


Base.metadata.create_all(bind=engine)
try:                                               # older databases: add the new column once
    from sqlalchemy import text as _sqltext
    with engine.begin() as _c:
        _c.execute(_sqltext("ALTER TABLE backup_log ADD COLUMN file_id VARCHAR DEFAULT ''"))
except Exception:
    pass                                           # column already exists - nothing to do


def _migrate_user_columns():
    """Adds the new session columns to an already-existing users table (SQLite/Postgres)."""
    from sqlalchemy import inspect, text
    cols = {c["name"] for c in inspect(engine).get_columns("users")}
    add = {"email": "VARCHAR DEFAULT ''", "session_id": "VARCHAR DEFAULT ''", "session_seen": "TIMESTAMP",
           "g_name": "VARCHAR DEFAULT ''", "g_picture": "VARCHAR DEFAULT ''", "logged_out_at": "TIMESTAMP",
           "name": "VARCHAR DEFAULT ''", "dept": "VARCHAR DEFAULT ''", "designation": "VARCHAR DEFAULT ''",
           "contact_email": "VARCHAR DEFAULT ''", "status": "VARCHAR DEFAULT 'approved'"}
    with engine.begin() as conn:
        for name, ddl in add.items():
            if name not in cols:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))


_migrate_user_columns()

# ================================================================
# 4. SCHEMAS (Pydantic) — request / response shapes
# ================================================================
class MedicineIn(BaseModel):
    name: str
    category: Optional[str] = ""
    batch: Optional[str] = ""
    qty: int = 0
    min_alert: int = 10
    price: float = 0.0
    expiry: Optional[str] = ""
    dose: Optional[str] = ""
    note: Optional[str] = ""
    img: Optional[str] = ""


class MedicineOut(MedicineIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: Optional[str] = None


class DoctorIn(BaseModel):
    name: str
    specialization: Optional[str] = ""
    contact: Optional[str] = ""
    days: Optional[str] = ""
    timing: Optional[str] = ""


class DoctorOut(DoctorIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class StudentIn(BaseModel):
    name: str
    roll: Optional[str] = ""
    dept: Optional[str] = ""
    year: Optional[str] = ""
    blood: Optional[str] = ""
    bday: Optional[str] = ""
    phone: Optional[str] = ""
    ec: Optional[str] = ""
    allergy: Optional[str] = ""
    addr: Optional[str] = ""
    img: Optional[str] = ""


class StudentOut(StudentIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    visits: Optional[int] = 0


class DispenseItemIn(BaseModel):
    medicine_id: int
    qty: int = 1
    sched: Optional[str] = ""


class DispenseIn(BaseModel):
    student_id: int
    doctor_name: Optional[str] = ""
    note: Optional[str] = ""
    items: List[DispenseItemIn]


class DispenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    student_id: int
    medicine_id: int
    doctor_name: Optional[str] = ""
    qty: int
    sched: Optional[str] = ""
    note: Optional[str] = ""
    dispensed_at: datetime
    student_name: Optional[str] = None
    medicine_name: Optional[str] = None


class NoticeIn(BaseModel):
    title: str
    message: Optional[str] = ""
    color: Optional[str] = "yellow"
    posted_by: Optional[str] = ""


class NoticeOut(NoticeIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    posted_at: datetime


class ActivityLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user: Optional[str] = ""
    action: str
    type: str
    timestamp: datetime


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "nurse"
    name: Optional[str] = ""
    dept: Optional[str] = ""
    designation: Optional[str] = ""
    email: Optional[str] = ""


class RegisterIn(BaseModel):
    name: str
    username: str
    password: str
    email: Optional[str] = ""
    dept: Optional[str] = ""
    designation: Optional[str] = ""
    role: Optional[str] = "doctor"      # requested console: doctor (Staff Console) | nurse (Medical Ward Console)


class ApproveIn(BaseModel):
    role: Optional[str] = None          # admin may change doctor <-> nurse while approving


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class GoogleLogin(BaseModel):
    credential: str                 # the Google ID token from the "Continue with Google" button
    role: Optional[str] = "nurse"   # admin | doctor | nurse — chosen on the login screen


# ================================================================
# 5. AUTH HELPERS
# ================================================================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, pw_hash: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8")[:72], pw_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    to_encode = data.copy()
    to_encode["iat"] = datetime.utcnow()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=expires_minutes)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ---- Remembered login (per laptop/browser) ----
# The browser keeps its token, so reopening the site on the same laptop goes straight to the dashboard.
# Several people/devices may be logged in at the same time; the token is renewed on every open (/auth/refresh).
def start_session(db: Session, user: User, email: str = "") -> str:
    """Records the Google email on the user row (if any). No login blocking."""
    if email and user.email != email:
        user.email = email
        db.commit()
    return ""


def seed_default_users(db: Session):
    """Default logins:  admin / admin123,  staff / staff123 (Staff Console),  medicalward / ward123 (Medical Ward Console).
    The two console accounts are created ONLY on a brand-new database, so an admin who removes them
    (or presses 'Reset users') does not get them back with the default password on the next restart.
    Older 'doctor' and 'nurse' accounts are still renamed to 'staff' and 'medicalward' (same roles, new password)."""
    fresh = db.query(User).count() == 0
    if not db.query(User).filter(User.username == "admin").first():
        db.add(User(username="admin", password_hash=hash_password("admin123"), role="admin",
                    name="System Owner", dept="Administration", designation="Owner / Admin", status="approved"))
    for old_name, uname, pw, role, disp in [("doctor", "staff", "staff123", "doctor", "Staff Console"),
                                            ("nurse", "medicalward", "ward123", "nurse", "Medical Ward Console")]:
        if db.query(User).filter(User.username == uname).first():
            continue
        u = db.query(User).filter(User.username == old_name).first()
        if u:
            u.username = uname
            u.password_hash = hash_password(pw)
        elif fresh:
            db.add(User(username=uname, password_hash=hash_password(pw), role=role, name=disp, status="approved"))
    db.commit()


OWNER_USERNAME = "admin"
MAX_PENDING_REGISTRATIONS = 100   # stops the public /auth/register form from being used to flood the database


def ensure_approved(user: User):
    """Registration approval gate (same messages as the Student Conduct app)."""
    st = (user.status or "approved").lower()
    if st == "pending":
        raise HTTPException(status_code=403, detail="Your registration is pending Admin approval")
    if st == "rejected":
        raise HTTPException(status_code=403, detail="Your registration was rejected. Contact Admin.")


def find_user_for_login(db: Session, ident: str) -> Optional[User]:
    """Username first; if the text looks like an e-mail, also the registration e-mail or the linked Google e-mail."""
    ident = (ident or "").strip().lower()
    if not ident:
        return None
    u = db.query(User).filter(func.lower(User.username) == ident).first()
    if u or "@" not in ident:
        return u
    return (db.query(User).filter(func.lower(User.contact_email) == ident).first()
            or db.query(User).filter(func.lower(User.email) == ident).first())


def user_public(u: User) -> dict:
    return {"id": u.id, "name": u.name or u.username, "username": u.username, "role": u.role,
            "dept": u.dept or "", "designation": u.designation or "",
            "email": u.contact_email or u.email or "", "google": bool(u.email),
            "status": (u.status or "approved").lower(),
            "created_at": u.created_at.isoformat() if u.created_at else None}


def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    cred_exc = HTTPException(status_code=401, detail="Could not validate credentials",
                              headers={"WWW-Authenticate": "Bearer"})
    if not token:
        raise cred_exc
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise cred_exc
    except JWTError:
        raise cred_exc
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise cred_exc
    if (user.status or "approved").lower() != "approved":
        raise HTTPException(status_code=401, detail="Account is not active", headers={"WWW-Authenticate": "Bearer"})
    if user.logged_out_at is not None and int(payload.get("iat", 0)) < calendar.timegm(user.logged_out_at.utctimetuple()):
        raise HTTPException(status_code=401, detail="Logged out from all devices",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require_role(*roles):
    def checker(user: User = Depends(get_current_user)):
        if roles and user.role not in roles:
            raise HTTPException(status_code=403, detail="Not enough permissions for this action")
        return user
    return checker


def verify_google_token(credential: str) -> dict:
    """Verify a Google ID token and return its claims.
    Uses the official google-auth library when it is installed; otherwise falls back to
    Google's tokeninfo endpoint (no extra dependency needed)."""
    try:
        from google.oauth2 import id_token as _google_id_token
        from google.auth.transport import requests as _google_requests
    except ImportError:
        _google_id_token = None

    if _google_id_token is not None:
        try:
            return _google_id_token.verify_oauth2_token(credential, _google_requests.Request(), GOOGLE_CLIENT_ID)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid Google token")

    try:
        url = "https://oauth2.googleapis.com/tokeninfo?" + urllib.parse.urlencode({"id_token": credential})
        with urllib.request.urlopen(url, timeout=10) as resp:
            info = json.loads(resp.read().decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    if info.get("aud") != GOOGLE_CLIENT_ID or info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(status_code=401, detail="Google token is not for this app")
    info["email_verified"] = str(info.get("email_verified", "")).lower() == "true"
    return info


# ================================================================
# 6. APP INIT
# ================================================================
app = FastAPI(
    title="RKMS MediStock Pro API",
    description="Local backend for the 789 / RKMS MediStock Pro Electron app",
    version="1.0.0",
)

# Local-only CORS — Electron's file:// / localhost renderer talks to 127.0.0.1 only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # app runs entirely on localhost inside Electron; tighten if you expose it further
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

with SessionLocal() as _db:
    seed_default_users(_db)

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))


@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse(os.path.join(_PKG_DIR, "app.html"))


@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}


_PRIVACY_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Privacy Policy - RKMS MediStock Pro</title>
<style>
body{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,Segoe UI,Roboto,sans-serif;line-height:1.65}
main{max-width:760px;margin:0 auto;padding:40px 20px}
h1{font-size:28px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 6px;color:#93c5fd}
p,li{color:#cbd5e1}a{color:#93c5fd}.muted{color:#94a3b8;font-size:14px}
</style></head><body><main>
<h1>Privacy Policy</h1>
<p class="muted">RKMS MediStock Pro &middot; Last updated: November 2026</p>

<h2>About this app</h2>
<p>RKMS MediStock Pro is used by the Ramakrishna Mission Health Center to manage medicine stock,
dispensing and student health records. It is meant for authorised staff only.</p>

<h2>What we collect</h2>
<ul>
<li><b>Google sign-in:</b> when you choose "Continue with Google", we receive your Google email address.
We use it only to sign you in and to record who performed an action in the activity log.
We do not receive your Google password.</li>
<li><b>Health center records:</b> medicine inventory, student details, dispensing and prescription
records that staff enter into the app.</li>
</ul>

<h2>How we use it</h2>
<p>Only to operate the health center's medicine and student-care workflow. We do not sell your data,
and we do not use it for advertising.</p>

<h2>Sharing</h2>
<p>Data is not shared with third parties, except where required by law.</p>

<h2>Storage and security</h2>
<p>Data is stored on the server that runs this application and is available only to signed-in users.
You can ask us to delete your sign-in record at any time.</p>

<h2>Contact</h2>
<p>Questions or deletion requests: <a href="mailto:__CONTACT__">__CONTACT__</a></p>
</main></body></html>"""


@app.get("/privacy", include_in_schema=False)
def privacy_page():
    return HTMLResponse(_PRIVACY_HTML.replace("__CONTACT__", PRIVACY_CONTACT))


def log_action(db: Session, action: str, user: str = "", type_: str = "success"):
    # also record the Google e-mail of whoever did it (shown in the Activity Log)
    try:
        u = db.query(User).filter(User.username == user).first()
        if u and u.email and u.email not in user:
            user = f"{user} <{u.email}>"
    except Exception:
        pass
    db.add(ActivityLog(user=user, action=action, type=type_))
    db.commit()


def medicine_status(m: Medicine) -> str:
    if m.qty == 0:
        return "Out of Stock"
    if m.qty <= m.min_alert:
        return "Low Stock"
    if m.expiry:
        try:
            days = (datetime.strptime(m.expiry, "%Y-%m-%d").date() - date.today()).days
            if 0 <= days <= 30:
                return "Expiring Soon"
        except ValueError:
            pass
    return "OK"


# ================================================================
# 7. AUTH ROUTES
# ================================================================
@app.post("/auth/login", response_model=Token, tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = find_user_for_login(db, form.username)
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong username or password!")
    ensure_approved(user)
    sid = start_session(db, user)
    token = create_access_token({"sub": user.username, "role": user.role, "sid": sid})
    log_action(db, f"{user.role} logged in", user.username, "info")
    return Token(access_token=token, role=user.role, username=user.username)


@app.post("/auth/google", response_model=Token, tags=["Auth"])
def google_login(payload: GoogleLogin, db: Session = Depends(get_db)):
    """Google sign-in for REGISTERED accounts only.
    A Google account becomes registered when a logged-in user connects it from the dashboard
    (POST /auth/google/link). An unknown Google account is rejected - no account is created here."""
    info = verify_google_token(payload.credential)
    email = (info.get("email") or "").lower()
    if not email or not info.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google email is not verified")

    if GOOGLE_ALLOWED_DOMAINS and email.split("@")[-1] not in GOOGLE_ALLOWED_DOMAINS:
        raise HTTPException(status_code=403, detail="This Google account is not allowed")

    matches = db.query(User).filter(func.lower(User.email) == email).all()
    if not matches:
        raise HTTPException(status_code=403,
                            detail="This Google account is not registered. Log in with your username and password, then connect Google from the dashboard.")
    wanted = (payload.role or "").lower()
    user = next((u for u in matches if u.role == wanted), matches[0])   # the role is the registered one, never a self-chosen one

    ensure_approved(user)
    user.g_name = info.get("name") or user.g_name or ""
    user.g_picture = info.get("picture") or user.g_picture or ""
    sid = start_session(db, user, email)
    token = create_access_token({"sub": user.username, "role": user.role, "sid": sid})
    log_action(db, f"{user.role} logged in via Google", user.username, "info")
    return Token(access_token=token, role=user.role, username=user.username)


@app.post("/auth/users", tags=["Auth"])
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                 current: User = Depends(require_role("admin"))):
    if payload.role not in ("admin", "doctor", "nurse"):
        raise HTTPException(400, "Role must be admin, doctor or nurse")
    if db.query(User).filter(func.lower(User.username) == payload.username.strip().lower()).first():
        raise HTTPException(400, "Username already exists")
    u = User(username=payload.username.strip().lower(), password_hash=hash_password(payload.password), role=payload.role,
             name=(payload.name or "").strip(), dept=payload.dept or "", designation=payload.designation or "",
             contact_email=(payload.email or "").strip().lower(), status="approved")
    db.add(u)
    db.commit()
    log_action(db, f"New user created: {u.username} ({u.role})", current.username, "info")
    return {"ok": True, "id": u.id}


@app.post("/auth/register", tags=["Auth"])
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    """Public self-registration for new faculty / staff. The account stays 'pending' (cannot log in)
    until an Admin approves it. Admin can never be requested here."""
    name = (payload.name or "").strip()[:100]
    username = (payload.username or "").strip().lower()
    email = (payload.email or "").strip().lower()[:120]
    if not name or not username or not payload.password:
        raise HTTPException(400, "Name, Username and Password are required")
    if len(payload.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if len(username) > 40 or "@" in username or any(ch.isspace() for ch in username):
        raise HTTPException(400, "Username can't contain spaces or '@' (max 40 characters)")
    if email and ("@" not in email or "." not in email.split("@")[-1]):
        raise HTTPException(400, "Enter a valid email address or leave it blank")
    if db.query(User).filter(func.lower(User.username) == username).first():
        raise HTTPException(400, "Username already exists")
    if email and (db.query(User).filter(func.lower(User.contact_email) == email).first()
                  or db.query(User).filter(func.lower(User.email) == email).first()):
        raise HTTPException(400, "This email is already registered")
    if db.query(User).filter(User.status == "pending").count() >= MAX_PENDING_REGISTRATIONS:
        raise HTTPException(429, "Too many registrations are waiting for approval. Please contact the Admin.")
    role = (payload.role or "doctor").lower()
    if role not in ("doctor", "nurse"):
        role = "doctor"
    u = User(username=username, password_hash=hash_password(payload.password), role=role, name=name,
             dept=(payload.dept or "")[:60], designation=(payload.designation or "").strip()[:80],
             contact_email=email, status="pending")
    db.add(u)
    db.commit()
    log_action(db, f"Registration request: {name} ({username}) - waiting for approval", username, "info")
    return {"ok": True, "message": "Registration submitted! Wait for Admin approval, then login."}


@app.get("/auth/users", tags=["Auth"])
def list_users(db: Session = Depends(get_db), current: User = Depends(require_role("admin"))):
    rows = db.query(User).order_by(User.created_at.desc()).all()
    out = [user_public(u) for u in rows]
    order = {"pending": 0, "approved": 1, "rejected": 2}
    out.sort(key=lambda x: order.get(x["status"], 3))   # stable: newest first inside each group
    return out


def _target_user(db: Session, user_id: int) -> User:
    u = db.query(User).get(user_id)
    if not u:
        raise HTTPException(404, "User not found")
    return u


@app.post("/auth/users/{user_id}/approve", tags=["Auth"])
def approve_user(user_id: int, payload: Optional[ApproveIn] = None, db: Session = Depends(get_db),
                 current: User = Depends(require_role("admin"))):
    u = _target_user(db, user_id)
    if payload and payload.role:
        if payload.role not in ("doctor", "nurse"):
            raise HTTPException(400, "Role must be doctor or nurse")
        if u.role != "admin":
            u.role = payload.role
    u.status = "approved"
    db.commit()
    log_action(db, f"User approved: {u.username} ({u.role})", current.username, "info")
    return {"ok": True}


@app.post("/auth/users/{user_id}/reject", tags=["Auth"])
def reject_user(user_id: int, db: Session = Depends(get_db), current: User = Depends(require_role("admin"))):
    u = _target_user(db, user_id)
    if u.username == OWNER_USERNAME or u.id == current.id:
        raise HTTPException(400, "The owner / your own account can't be rejected")
    u.status = "rejected"
    db.commit()
    log_action(db, f"User rejected: {u.username}", current.username, "danger")
    return {"ok": True}


@app.post("/auth/users/reset", tags=["Auth"])
def reset_users(db: Session = Depends(get_db), current: User = Depends(require_role("admin"))):
    """Removes every user except the owner ('admin') and the admin pressing the button."""
    n = (db.query(User).filter(User.username != OWNER_USERNAME, User.id != current.id)
         .delete(synchronize_session=False))
    db.commit()
    log_action(db, f"All users reset ({n} removed, owner kept)", current.username, "danger")
    return {"ok": True, "removed": n}


@app.delete("/auth/users/{user_id}", tags=["Auth"])
def delete_user(user_id: int, db: Session = Depends(get_db), current: User = Depends(require_role("admin"))):
    u = _target_user(db, user_id)
    if u.username == OWNER_USERNAME or u.id == current.id:
        raise HTTPException(400, "The owner / your own account can't be removed")
    name = u.username
    db.delete(u)
    db.commit()
    log_action(db, f"User removed: {name}", current.username, "danger")
    return {"ok": True}


@app.post("/auth/change-password", tags=["Auth"])
def change_password(payload: ChangePasswordIn, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    if not verify_password(payload.current_password, current.password_hash):
        raise HTTPException(400, "Current password is wrong")
    if len(payload.new_password) < 6:
        raise HTTPException(400, "New password must be at least 6 characters")
    current.password_hash = hash_password(payload.new_password)
    db.commit()
    log_action(db, "Password changed", current.username, "info")
    return {"ok": True}


@app.get("/auth/me", tags=["Auth"])
def me(current: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Also used as the heartbeat + 'restore my session after refresh' call."""
    out = {"username": current.username, "role": current.role, "email": current.email or "",
           "name": current.name or current.username, "dept": current.dept or "", "designation": current.designation or "",
           "google": {"email": current.email or "", "name": current.g_name or "", "picture": current.g_picture or ""}
                     if current.email else None}
    if current.role == "admin":
        out["pending_users"] = db.query(User).filter(User.status == "pending").count()
    return out


@app.post("/auth/google/link", tags=["Auth"])
def google_link(payload: GoogleLogin, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    """Connect a Google account to the person who is ALREADY logged in (e.g. with username/password)."""
    info = verify_google_token(payload.credential)
    email = (info.get("email") or "").lower()
    if not email or not info.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google email is not verified")
    if GOOGLE_ALLOWED_DOMAINS and email.split("@")[-1] not in GOOGLE_ALLOWED_DOMAINS:
        raise HTTPException(status_code=403, detail="This Google account is not allowed")
    taken = db.query(User).filter(func.lower(User.email) == email, User.id != current.id).first()
    if taken and not taken.username.startswith(email + " ("):   # (old Google-created rows may be re-linked)
        raise HTTPException(status_code=409, detail="This Google account is already registered to another user")
    current.email = email
    current.g_name = info.get("name") or ""
    current.g_picture = info.get("picture") or ""
    db.commit()
    log_action(db, f"Google account linked: {email}", current.username, "info")
    return {"email": email, "name": current.g_name, "picture": current.g_picture}


@app.post("/auth/google/unlink", tags=["Auth"])
def google_unlink(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    current.email = ""
    current.g_name = ""
    current.g_picture = ""
    db.commit()
    log_action(db, "Google account disconnected", current.username, "info")
    return {"ok": True}


@app.post("/auth/logout", tags=["Auth"])
def logout(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    """Only the person pressing Logout leaves; the browser then forgets its token."""
    log_action(db, f"{current.role} logged out", current.username, "info")
    return {"ok": True}


@app.post("/auth/logout-all", tags=["Auth"])
def logout_all(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    """Optional: ends this account's login on EVERY laptop/browser, not just this one."""
    current.logged_out_at = datetime.utcnow()
    db.commit()
    log_action(db, f"{current.role} logged out from all devices", current.username, "info")
    return {"ok": True}


@app.post("/auth/refresh", response_model=Token, tags=["Auth"])
def refresh(current: User = Depends(get_current_user)):
    """Called every time the site opens on a remembered laptop: hands out a fresh 30-day token."""
    token = create_access_token({"sub": current.username, "role": current.role})
    return Token(access_token=token, role=current.role, username=current.username)


# ================================================================
# 8. DASHBOARD
# ================================================================
@app.get("/dashboard/summary", tags=["Dashboard"])
def dashboard_summary(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    meds = db.query(Medicine).all()
    total = len(meds)
    low = len([m for m in meds if m.qty > 0 and m.qty <= m.min_alert])
    out = len([m for m in meds if m.qty == 0])
    expiring = 0
    for m in meds:
        if m.expiry:
            try:
                d = (datetime.strptime(m.expiry, "%Y-%m-%d").date() - date.today()).days
                if 0 <= d <= 30:
                    expiring += 1
            except ValueError:
                pass
    students = db.query(Student).count()
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_count = db.query(DispenseRecord).filter(DispenseRecord.dispensed_at >= today_start).count()

    recent = (db.query(DispenseRecord)
              .order_by(DispenseRecord.dispensed_at.desc())
              .limit(5).all())
    recent_out = [{
        "student": r.student.name if r.student else "—",
        "medicine": r.medicine.name if r.medicine else "—",
        "qty": r.qty
    } for r in recent]

    return {
        "total_medicines": total,
        "low_stock": low,
        "out_of_stock": out,
        "expiring_30d": expiring,
        "students": students,
        "dispensed_today": today_count,
        "recent_dispense": recent_out,
    }


# ================================================================
# 9. MEDICINES CRUD
# ================================================================
@app.get("/medicines", response_model=List[MedicineOut], tags=["Medicines"])
def list_medicines(search: Optional[str] = None, category: Optional[str] = None,
                    db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    q = db.query(Medicine)
    if search:
        q = q.filter(Medicine.name.ilike(f"%{search}%"))
    if category and category != "All":
        q = q.filter(Medicine.category == category)
    meds = q.order_by(Medicine.name).all()
    out = []
    for m in meds:
        o = MedicineOut.model_validate(m)
        o.status = medicine_status(m)
        out.append(o)
    return out


@app.post("/medicines", response_model=MedicineOut, tags=["Medicines"])
def add_medicine(payload: MedicineIn, db: Session = Depends(get_db),
                  current: User = Depends(require_role("admin", "nurse"))):
    m = Medicine(**payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    log_action(db, f"Medicine added: {m.name}", current.username)
    o = MedicineOut.model_validate(m)
    o.status = medicine_status(m)
    return o


@app.put("/medicines/{med_id}", response_model=MedicineOut, tags=["Medicines"])
def update_medicine(med_id: int, payload: MedicineIn, db: Session = Depends(get_db),
                     current: User = Depends(require_role("admin", "nurse"))):
    m = db.query(Medicine).get(med_id)
    if not m:
        raise HTTPException(404, "Medicine not found")
    for k, v in payload.model_dump().items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    log_action(db, f"Medicine updated: {m.name}", current.username)
    o = MedicineOut.model_validate(m)
    o.status = medicine_status(m)
    return o


@app.delete("/medicines/{med_id}", tags=["Medicines"])
def delete_medicine(med_id: int, db: Session = Depends(get_db),
                     current: User = Depends(require_role("admin"))):
    m = db.query(Medicine).get(med_id)
    if not m:
        raise HTTPException(404, "Medicine not found")
    name = m.name
    db.delete(m)
    db.commit()
    log_action(db, f"Medicine deleted: {name}", current.username, "danger")
    return {"ok": True}


# ================================================================
# 10. DOCTORS CRUD
# ================================================================
@app.get("/doctors", response_model=List[DoctorOut], tags=["Doctors"])
def list_doctors(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    return db.query(Doctor).order_by(Doctor.name).all()


@app.post("/doctors", response_model=DoctorOut, tags=["Doctors"])
def add_doctor(payload: DoctorIn, db: Session = Depends(get_db),
                current: User = Depends(require_role("admin", "nurse"))):
    d = Doctor(**payload.model_dump())
    db.add(d)
    db.commit()
    db.refresh(d)
    log_action(db, f"Doctor added: {d.name}", current.username)
    return d


@app.delete("/doctors/{doc_id}", tags=["Doctors"])
def delete_doctor(doc_id: int, db: Session = Depends(get_db),
                   current: User = Depends(require_role("admin"))):
    d = db.query(Doctor).get(doc_id)
    if not d:
        raise HTTPException(404, "Doctor not found")
    db.delete(d)
    db.commit()
    log_action(db, f"Doctor removed: {d.name}", current.username, "danger")
    return {"ok": True}


# ================================================================
# 11. STUDENTS CRUD
# ================================================================
@app.get("/students", response_model=List[StudentOut], tags=["Students"])
def list_students(search: Optional[str] = None, db: Session = Depends(get_db),
                   current: User = Depends(get_current_user)):
    q = db.query(Student)
    if search:
        like = f"%{search}%"
        q = q.filter((Student.name.ilike(like)) | (Student.roll.ilike(like)))
    students = q.order_by(Student.name).all()
    out = []
    for s in students:
        o = StudentOut.model_validate(s)
        o.visits = db.query(DispenseRecord).filter(DispenseRecord.student_id == s.id).count()
        out.append(o)
    return out


@app.post("/students", response_model=StudentOut, tags=["Students"])
def add_student(payload: StudentIn, db: Session = Depends(get_db),
                 current: User = Depends(require_role("admin", "nurse"))):
    s = Student(**payload.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    log_action(db, f"Student added: {s.name}", current.username)
    o = StudentOut.model_validate(s)
    o.visits = 0
    return o


@app.put("/students/{stu_id}", response_model=StudentOut, tags=["Students"])
def update_student(stu_id: int, payload: StudentIn, db: Session = Depends(get_db),
                    current: User = Depends(require_role("admin", "nurse"))):
    s = db.query(Student).get(stu_id)
    if not s:
        raise HTTPException(404, "Student not found")
    for k, v in payload.model_dump().items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    log_action(db, f"Student updated: {s.name}", current.username)
    o = StudentOut.model_validate(s)
    o.visits = db.query(DispenseRecord).filter(DispenseRecord.student_id == s.id).count()
    return o


@app.delete("/students/{stu_id}", tags=["Students"])
def delete_student(stu_id: int, db: Session = Depends(get_db),
                    current: User = Depends(require_role("admin"))):
    s = db.query(Student).get(stu_id)
    if not s:
        raise HTTPException(404, "Student not found")
    name = s.name
    db.delete(s)
    db.commit()
    log_action(db, f"Student removed: {name}", current.username, "danger")
    return {"ok": True}


# ================================================================
# 12. DISPENSE
# ================================================================
@app.post("/dispense", tags=["Dispense"])
def dispense(payload: DispenseIn, db: Session = Depends(get_db),
             current: User = Depends(require_role("admin", "doctor", "nurse"))):
    student = db.query(Student).get(payload.student_id)
    if not student:
        raise HTTPException(404, "Student not found")
    if not payload.items:
        raise HTTPException(400, "No medicines selected")

    dispensed_names = []
    for item in payload.items:
        med = db.query(Medicine).get(item.medicine_id)
        if not med:
            continue
        if med.qty < item.qty:
            raise HTTPException(400, f"Not enough stock for {med.name} (have {med.qty}, need {item.qty})")
        med.qty -= item.qty
        rec = DispenseRecord(
            student_id=student.id, medicine_id=med.id, doctor_name=payload.doctor_name or "",
            qty=item.qty, sched=item.sched or "", note=payload.note or ""
        )
        db.add(rec)
        dispensed_names.append(f"{med.name} x{item.qty}")

    if not dispensed_names:
        raise HTTPException(400, "No valid medicines were dispensed")

    db.commit()
    log_action(db, f"Dispensed to {student.name}: {', '.join(dispensed_names)}", current.username)
    return {"ok": True, "dispensed": dispensed_names}


@app.get("/dispense/history", response_model=List[DispenseOut], tags=["Dispense"])
def dispense_history(search: Optional[str] = None, db: Session = Depends(get_db),
                      current: User = Depends(get_current_user)):
    q = db.query(DispenseRecord).order_by(DispenseRecord.dispensed_at.desc())
    records = q.all()
    out = []
    for r in records:
        if search:
            hay = f"{r.student.name if r.student else ''} {r.medicine.name if r.medicine else ''}".lower()
            if search.lower() not in hay:
                continue
        o = DispenseOut.model_validate(r)
        o.student_name = r.student.name if r.student else None
        o.medicine_name = r.medicine.name if r.medicine else None
        out.append(o)
    return out


@app.delete("/dispense/history/{rec_id}", tags=["Dispense"])
def delete_dispense_record(rec_id: int, db: Session = Depends(get_db),
                            current: User = Depends(require_role("admin"))):
    r = db.query(DispenseRecord).get(rec_id)
    if not r:
        raise HTTPException(404, "Record not found")
    db.delete(r)
    db.commit()
    log_action(db, "Dispense record deleted", current.username, "danger")
    return {"ok": True}


# ================================================================
# 13. PRESCRIPTIONS (grouped view of dispense history, per visit)
# ================================================================
@app.get("/prescriptions", tags=["Prescriptions"])
def prescriptions(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    records = db.query(DispenseRecord).order_by(DispenseRecord.dispensed_at.desc()).all()
    groups = {}
    for r in records:
        day_key = r.dispensed_at.strftime("%Y-%m-%d")
        key = f"{r.student_id}_{day_key}"
        if key not in groups:
            groups[key] = {
                "student": r.student.name if r.student else "—",
                "roll": r.student.roll if r.student else "",
                "dept": r.student.dept if r.student else "",
                "year": r.student.year if r.student else "",
                "doctor": r.doctor_name,
                "date": r.dispensed_at.strftime("%d %b %Y"),
                "note": r.note,
                "meds": [],
            }
        groups[key]["meds"].append({
            "name": r.medicine.name if r.medicine else "—",
            "qty": r.qty,
            "sched": r.sched,
        })
    return list(groups.values())


# ================================================================
# 14. DAILY REPORT
# ================================================================
@app.get("/reports/daily", tags=["Reports"])
def daily_report(day: Optional[str] = None, db: Session = Depends(get_db),
                  current: User = Depends(get_current_user)):
    target = datetime.strptime(day, "%Y-%m-%d").date() if day else date.today()
    start = datetime.combine(target, datetime.min.time())
    end = start + timedelta(days=1)
    records = (db.query(DispenseRecord)
               .filter(DispenseRecord.dispensed_at >= start, DispenseRecord.dispensed_at < end)
               .all())
    total_qty = sum(r.qty for r in records)
    return {
        "date": target.isoformat(),
        "total_transactions": len(records),
        "total_units_dispensed": total_qty,
        "records": [{
            "student": r.student.name if r.student else "—",
            "medicine": r.medicine.name if r.medicine else "—",
            "qty": r.qty,
            "doctor": r.doctor_name,
            "time": r.dispensed_at.strftime("%H:%M"),
        } for r in records]
    }


# ================================================================
# 15. ANALYTICS
# ================================================================
@app.get("/analytics/top-medicines", tags=["Analytics"])
def top_medicines(limit: int = 5, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    rows = (db.query(Medicine.name, func.sum(DispenseRecord.qty).label("total"))
            .join(DispenseRecord, DispenseRecord.medicine_id == Medicine.id)
            .group_by(Medicine.name)
            .order_by(func.sum(DispenseRecord.qty).desc())
            .limit(limit).all())
    return [{"medicine": r[0], "total": int(r[1])} for r in rows]


@app.get("/analytics/dept-usage", tags=["Analytics"])
def dept_usage(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    rows = (db.query(Student.dept, func.sum(DispenseRecord.qty).label("total"))
            .join(DispenseRecord, DispenseRecord.student_id == Student.id)
            .group_by(Student.dept)
            .order_by(func.sum(DispenseRecord.qty).desc())
            .all())
    return [{"dept": r[0] or "—", "total": int(r[1])} for r in rows]


@app.get("/analytics/monthly-trend", tags=["Analytics"])
def monthly_trend(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    records = db.query(DispenseRecord).all()
    buckets = {}
    for r in records:
        key = r.dispensed_at.strftime("%Y-%m")
        buckets[key] = buckets.get(key, 0) + r.qty
    return [{"month": k, "total": v} for k, v in sorted(buckets.items())]


@app.get("/analytics/year-wise", tags=["Analytics"])
def year_wise(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    rows = (db.query(Student.year, func.sum(DispenseRecord.qty).label("total"))
            .join(DispenseRecord, DispenseRecord.student_id == Student.id)
            .group_by(Student.year)
            .order_by(Student.year)
            .all())
    return [{"year": r[0] or "—", "total": int(r[1])} for r in rows]


# ================================================================
# 16. STOCK VALUE
# ================================================================
@app.get("/stock/value", tags=["Stock"])
def stock_value(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    meds = db.query(Medicine).all()
    rows = []
    total = 0.0
    for m in meds:
        val = round(m.qty * (m.price or 0), 2)
        total += val
        rows.append({
            "medicine": m.name, "category": m.category, "qty": m.qty,
            "price": m.price, "value": val, "status": medicine_status(m)
        })
    return {"total_value": round(total, 2), "medicines": rows}


# ================================================================
# 17. BIRTHDAYS
# ================================================================
@app.get("/students/birthdays/upcoming", tags=["Students"])
def upcoming_birthdays(within_days: int = 7, db: Session = Depends(get_db),
                        current: User = Depends(get_current_user)):
    today = date.today()
    out = []
    for s in db.query(Student).filter(Student.bday != "").all():
        try:
            bd = datetime.strptime(s.bday, "%Y-%m-%d").date()
        except ValueError:
            continue
        next_bday = bd.replace(year=today.year)
        if next_bday < today:
            next_bday = next_bday.replace(year=today.year + 1)
        days_left = (next_bday - today).days
        if days_left <= within_days:
            out.append({"name": s.name, "dept": s.dept, "year": s.year, "bday": s.bday, "days_left": days_left})
    return sorted(out, key=lambda x: x["days_left"])


# ================================================================
# 18. NOTICE BOARD
# ================================================================
@app.get("/notices", response_model=List[NoticeOut], tags=["Notices"])
def list_notices(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    return db.query(Notice).order_by(Notice.posted_at.desc()).all()


@app.post("/notices", response_model=NoticeOut, tags=["Notices"])
def add_notice(payload: NoticeIn, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    n = Notice(**payload.model_dump())
    db.add(n)
    db.commit()
    db.refresh(n)
    log_action(db, f"Notice posted: {n.title}", current.username)
    return n


@app.delete("/notices/{notice_id}", tags=["Notices"])
def delete_notice(notice_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    n = db.query(Notice).get(notice_id)
    if not n:
        raise HTTPException(404, "Notice not found")
    db.delete(n)
    db.commit()
    return {"ok": True}


# ================================================================
# 19. ACTIVITY LOG
# ================================================================
@app.get("/activity-log", response_model=List[ActivityLogOut], tags=["Activity Log"])
def activity_log(limit: int = 300, db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    return (db.query(ActivityLog)
            .order_by(ActivityLog.timestamp.desc())
            .limit(limit).all())


@app.delete("/activity-log", tags=["Activity Log"])
def clear_activity_log(db: Session = Depends(get_db), current: User = Depends(require_role("admin"))):
    db.query(ActivityLog).delete()
    db.commit()
    return {"ok": True}


# ================================================================
# 20. CSV EXPORTS  (medicines / students / history)
# ================================================================
def _csv_response(rows: list, header: list, filename: str):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get("/reports/export/medicines", tags=["Reports"])
def export_medicines_csv(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    meds = db.query(Medicine).all()
    rows = [[m.name, m.batch, m.category, m.qty, m.min_alert, m.price,
             round(m.qty * (m.price or 0), 2), m.dose, m.expiry, medicine_status(m)] for m in meds]
    header = ["Name", "Batch", "Category", "Stock", "Min", "Price", "Value", "Dosage", "Expiry", "Status"]
    return _csv_response(rows, header, f"RKMS_Medicines_{date.today()}.csv")


@app.get("/reports/export/students", tags=["Reports"])
def export_students_csv(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    students = db.query(Student).all()
    rows = [[s.name, s.roll, s.dept, s.year, s.blood, s.phone, s.ec, s.allergy, s.bday, s.addr] for s in students]
    header = ["Name", "Roll", "Dept", "Year", "Blood", "Phone", "Emergency", "Allergy", "Birthday", "Address"]
    return _csv_response(rows, header, f"RKMS_Students_{date.today()}.csv")


@app.get("/reports/export/history", tags=["Reports"])
def export_history_csv(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    records = db.query(DispenseRecord).order_by(DispenseRecord.dispensed_at.desc()).all()
    rows = [[
        r.student.name if r.student else "", r.student.roll if r.student else "",
        r.student.dept if r.student else "", r.student.year if r.student else "",
        r.medicine.name if r.medicine else "", r.qty, r.sched, r.doctor_name, r.note,
        r.dispensed_at.strftime("%d-%m-%Y %H:%M")
    ] for r in records]
    header = ["Student", "Roll", "Dept", "Year", "Medicine", "Qty", "Schedule", "Doctor", "Notes", "DateTime"]
    return _csv_response(rows, header, f"RKMS_History_{date.today()}.csv")


# ================================================================
# 21. BACKUP / RESTORE  (whole SQLite file — simplest, safest backup)
# ================================================================
@app.get("/backup/download", tags=["Backup"])
def backup_download(current: User = Depends(require_role("admin"))):
    if not DATABASE_URL.startswith("sqlite"):
        raise HTTPException(400, "Whole-file backup only applies to SQLite mode. Use /backup/export-json instead, or back up your PostgreSQL server directly (e.g. pg_dump).")
    if not os.path.exists(DB_PATH):
        raise HTTPException(404, "Database file not found")
    return FileResponse(
        DB_PATH, media_type="application/octet-stream",
        filename=f"RKMS_MediStock_Backup_{date.today()}.db"
    )


@app.post("/backup/restore", tags=["Backup"])
def backup_restore(file: UploadFile = File(...), current: User = Depends(require_role("admin"))):
    if not DATABASE_URL.startswith("sqlite"):
        raise HTTPException(400, "Whole-file restore only applies to SQLite mode. Restore your PostgreSQL server directly (e.g. pg_restore).")
    if not file.filename.endswith(".db"):
        raise HTTPException(400, "Please upload a .db backup file created by this app")
    global engine, SessionLocal
    engine.dispose()
    tmp_path = DB_PATH + ".incoming"
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    shutil.move(tmp_path, DB_PATH)
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SessionLocal.configure(bind=engine)
    return {"ok": True, "message": "Database restored. Please restart the app."}


def _backup_payload(db: Session, current: User) -> dict:
    return {
        "exported_at": datetime.utcnow().isoformat(),
        "exported_by": current.username,
        "medicines": [MedicineOut.model_validate(m).model_dump(mode="json") for m in db.query(Medicine).all()],
        "students": [StudentOut.model_validate(s).model_dump(mode="json") for s in db.query(Student).all()],
        "doctors": [DoctorOut.model_validate(d).model_dump(mode="json") for d in db.query(Doctor).all()],
        "notices": [NoticeOut.model_validate(n).model_dump(mode="json") for n in db.query(Notice).all()],
    }


@app.get("/backup/export-json", tags=["Backup"])
def backup_export_json(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    """A human-readable JSON backup, mirrors the original app's 'Download Backup (JSON)' button."""
    buf = io.StringIO(json.dumps(_backup_payload(db, current), indent=2, default=str))
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="RKMS_Backup_{date.today()}.json"'}
    )


# ----------------------------------------------------------------
# ONE-CLICK BACKUP TO A SINGLE SHARED GOOGLE DRIVE  (done by the SERVER)
# Any logged-in user can press "Backup now"; nobody needs their own Google setup.
# Set ONE of these up once (by the admin), as environment variables:
#   A) Service account  : GOOGLE_SERVICE_ACCOUNT_JSON (key JSON text) or GOOGLE_SERVICE_ACCOUNT_FILE (path)
#                         + GOOGLE_DRIVE_FOLDER_ID  (folder in a *Shared drive*, shared with the service account)
#   B) Owner's Drive    : GOOGLE_CLIENT_SECRET + GOOGLE_DRIVE_REFRESH_TOKEN  (+ optional GOOGLE_DRIVE_FOLDER_ID)
# If neither is set, the button still works: the browser downloads the backup file instead.
# ----------------------------------------------------------------
GOOGLE_SA_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SA_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_DRIVE_REFRESH_TOKEN = os.environ.get("GOOGLE_DRIVE_REFRESH_TOKEN", "")
GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
DRIVE_FOLDER_NAME = "RKMS MediStock Backups"
_last_drive = {"t": 0.0, "name": "", "link": ""}


def _drive_configured() -> bool:
    return bool(GOOGLE_SA_JSON.strip() or (GOOGLE_SA_FILE and os.path.exists(GOOGLE_SA_FILE))
                or (GOOGLE_CLIENT_SECRET and GOOGLE_DRIVE_REFRESH_TOKEN))


def _drive_token() -> Optional[str]:
    sa = GOOGLE_SA_JSON.strip()
    if not sa and GOOGLE_SA_FILE and os.path.exists(GOOGLE_SA_FILE):
        with open(GOOGLE_SA_FILE, encoding="utf-8") as fh:
            sa = fh.read()
    if sa:
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request as _GReq
        except ImportError:
            raise HTTPException(500, "Server needs:  pip install google-auth requests")
        creds = service_account.Credentials.from_service_account_info(
            json.loads(sa), scopes=["https://www.googleapis.com/auth/drive"])
        creds.refresh(_GReq())
        return creds.token
    if GOOGLE_CLIENT_SECRET and GOOGLE_DRIVE_REFRESH_TOKEN:
        data = urllib.parse.urlencode({
            "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": GOOGLE_DRIVE_REFRESH_TOKEN, "grant_type": "refresh_token"}).encode()
        with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=data), timeout=20) as r:
            return json.loads(r.read())["access_token"]
    return None


def _gd(token: str, method: str, url: str, body: Optional[bytes] = None, ctype: str = "application/json", raw: bool = False):
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Authorization": "Bearer " + token, "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            return data if raw else json.loads(data or b"{}")
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read()).get("error", {})
            why = (err.get("errors") or [{}])[0].get("reason") or err.get("status") or ""
            msg = f"{err.get('message', '')} ({why})".strip()
        except Exception:
            msg = ""
        raise HTTPException(502, f"Google Drive error {e.code}: {msg or e.reason}")


class DriveBackupIn(BaseModel):
    auto: bool = False


def _backup_row(b: "BackupLog") -> dict:
    return {"id": b.id, "at": (b.at.isoformat() + "Z") if b.at else "", "user": b.username, "ok": bool(b.ok),
            "verified": bool(b.verified), "name": b.name, "size": b.size or 0, "summary": b.summary,
            "link": b.link, "error": b.error, "has_file": bool(getattr(b, "file_id", ""))}


@app.get("/backup/status", tags=["Backup"])
def backup_status(db: Session = Depends(get_db), current: User = Depends(get_current_user)):
    last = db.query(BackupLog).filter(BackupLog.ok == True).order_by(BackupLog.id.desc()).first()   # noqa: E712
    return {"drive_ready": _drive_configured(), "last": _backup_row(last) if last else None}


@app.get("/backup/history", tags=["Backup"])
def backup_history(limit: int = Query(15, ge=1, le=100), db: Session = Depends(get_db),
                   current: User = Depends(get_current_user)):
    """Newest first. Shows who backed up, when, whether it succeeded and whether Drive really has the file."""
    rows = db.query(BackupLog).order_by(BackupLog.id.desc()).limit(limit).all()
    return {"drive_ready": _drive_configured(), "items": [_backup_row(r) for r in rows]}


@app.get("/backup/file/{log_id}", tags=["Backup"])
def backup_file(log_id: int, download: bool = Query(False), db: Session = Depends(get_db),
                current: User = Depends(get_current_user)):
    """Open (or download) the backup file that was saved to Google Drive. The server reads it from
    Drive, so the person looking at it needs no Google account or Drive permission."""
    row = db.query(BackupLog).filter(BackupLog.id == log_id, BackupLog.ok == True).first()   # noqa: E712
    if not row or not row.file_id:
        raise HTTPException(404, "This backup file is not available")
    token = _drive_token()
    if not token:
        raise HTTPException(400, "Google Drive is not set up on the server")
    data = _gd(token, "GET", f"https://www.googleapis.com/drive/v3/files/{row.file_id}?alt=media&supportsAllDrives=true", raw=True)
    disp = "attachment" if download else "inline"
    return StreamingResponse(iter([data]), media_type="application/json",
                             headers={"Content-Disposition": f'{disp}; filename="{row.name}"'})


@app.post("/backup/drive", tags=["Backup"])
def backup_to_drive(body: DriveBackupIn = DriveBackupIn(), db: Session = Depends(get_db),
                    current: User = Depends(get_current_user)):
    """Any logged-in user: save a full JSON backup into the ONE shared Google Drive and verify it arrived."""
    if not _drive_configured():
        return {"ok": False, "mode": "download", "reason": "Drive backup is not set up on the server yet."}
    gap = 1500 if body.auto else 15            # seconds between two real uploads
    if _last_drive["name"] and time.time() - _last_drive["t"] < gap:
        return {"ok": True, "mode": "drive", "recent": True, "verified": _last_drive.get("verified", False),
                "name": _last_drive["name"], "link": _last_drive["link"]}
    row = BackupLog(username=current.username, ok=False)
    try:
        token = _drive_token()
        api = "https://www.googleapis.com/drive/v3/files"
        folder = GOOGLE_DRIVE_FOLDER_ID.strip()
        if not folder:                          # owner mode: find or create the folder by name
            q = urllib.parse.quote(f"name='{DRIVE_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false")
            found = _gd(token, "GET", f"{api}?q={q}&fields=files(id)&supportsAllDrives=true&includeItemsFromAllDrives=true").get("files", [])
            folder = found[0]["id"] if found else _gd(
                token, "POST", f"{api}?fields=id&supportsAllDrives=true",
                json.dumps({"name": DRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}).encode())["id"]
        data = _backup_payload(db, current)
        payload = json.dumps(data, indent=1, default=str)
        raw = payload.encode("utf-8")
        row.name = "RKMS_Backup_" + datetime.now().strftime("%Y-%m-%d_%H-%M") + ".json"
        row.size = len(raw)
        row.summary = (f"{len(data['medicines'])} medicines, {len(data['students'])} students, "
                       f"{len(data['doctors'])} doctors, {len(data['notices'])} notices")
        b = "rkms" + secrets.token_hex(8)
        mp = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
              + json.dumps({"name": row.name, "parents": [folder]})
              + f"\r\n--{b}\r\nContent-Type: application/json\r\n\r\n").encode("utf-8") + raw + f"\r\n--{b}--".encode()
        up = _gd(token, "POST", "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id&supportsAllDrives=true",
                 mp, f"multipart/related; boundary={b}")
        # VERIFY: ask Drive for the file we just wrote and compare its size
        chk = _gd(token, "GET", f"{api}/{up['id']}?fields=id,name,size,trashed&supportsAllDrives=true")
        row.verified = (not chk.get("trashed")) and int(chk.get("size", -1)) == len(raw)
        row.link = f"https://drive.google.com/drive/folders/{folder}"
        row.file_id = up["id"]
        row.ok = True
    except HTTPException as e:
        row.error = str(e.detail)[:400]
        db.add(row); db.commit()
        raise
    except Exception as e:
        row.error = f"{type(e).__name__}: {e}"[:400]
        db.add(row); db.commit()
        raise HTTPException(502, "Backup failed: " + row.error)
    db.add(row)
    log_action(db, f"Backup saved to Google Drive by {current.username} ({row.summary})", current.username, "info")
    db.commit()
    _last_drive.update(t=time.time(), name=row.name, link=row.link, verified=row.verified)
    return {"ok": True, "mode": "drive", "name": row.name, "link": row.link, "verified": row.verified,
            "size": row.size, "summary": row.summary}


# ================================================================
# 22. HEALTH CHECK  (handy for Electron to confirm backend is up)
# ================================================================
@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# ================================================================
# 23. ENTRYPOINT
# ================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
