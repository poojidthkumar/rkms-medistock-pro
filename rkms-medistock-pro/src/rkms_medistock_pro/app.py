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
   doctor / doc123
   nurse  / nurse123
================================================================
"""

import os
import io
import csv
import json
import shutil
from datetime import datetime, timedelta, date
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
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

SECRET_KEY = os.environ.get("RKMS_SECRET_KEY", "rkms-medistock-change-this-secret-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 12 * 60  # 12 hours — matches the 30-min idle logout in the frontend session

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


Base.metadata.create_all(bind=engine)

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


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


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
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=expires_minutes)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def seed_default_users(db: Session):
    """Matches the hardcoded logins in the original 789.html so nothing breaks for existing users."""
    defaults = [("admin", "admin123", "admin"), ("doctor", "doc123", "doctor"), ("nurse", "nurse123", "nurse")]
    for uname, pw, role in defaults:
        if not db.query(User).filter(User.username == uname).first():
            db.add(User(username=uname, password_hash=hash_password(pw), role=role))
    db.commit()


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
    return user


def require_role(*roles):
    def checker(user: User = Depends(get_current_user)):
        if roles and user.role not in roles:
            raise HTTPException(status_code=403, detail="Not enough permissions for this action")
        return user
    return checker


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


def log_action(db: Session, action: str, user: str = "", type_: str = "success"):
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
    user = db.query(User).filter(User.username == form.username.lower()).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong username or password!")
    token = create_access_token({"sub": user.username, "role": user.role})
    log_action(db, f"{user.role} logged in", user.username, "info")
    return Token(access_token=token, role=user.role, username=user.username)


@app.post("/auth/users", tags=["Auth"])
def create_user(payload: UserCreate, db: Session = Depends(get_db),
                 current: User = Depends(require_role("admin"))):
    if db.query(User).filter(User.username == payload.username.lower()).first():
        raise HTTPException(400, "Username already exists")
    u = User(username=payload.username.lower(), password_hash=hash_password(payload.password), role=payload.role)
    db.add(u)
    db.commit()
    log_action(db, f"New user created: {u.username} ({u.role})", current.username, "info")
    return {"ok": True, "id": u.id}


@app.get("/auth/me", tags=["Auth"])
def me(current: User = Depends(get_current_user)):
    return {"username": current.username, "role": current.role}


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


@app.get("/backup/export-json", tags=["Backup"])
def backup_export_json(db: Session = Depends(get_db), current: User = Depends(require_role("admin"))):
    """A human-readable JSON backup, mirrors the original app's 'Download Backup (JSON)' button."""
    data = {
        "exported_at": datetime.utcnow().isoformat(),
        "medicines": [MedicineOut.model_validate(m).model_dump(mode="json") for m in db.query(Medicine).all()],
        "students": [StudentOut.model_validate(s).model_dump(mode="json") for s in db.query(Student).all()],
        "doctors": [DoctorOut.model_validate(d).model_dump(mode="json") for d in db.query(Doctor).all()],
        "notices": [NoticeOut.model_validate(n).model_dump(mode="json") for n in db.query(Notice).all()],
    }
    buf = io.StringIO(json.dumps(data, indent=2, default=str))
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="RKMS_Backup_{date.today()}.json"'}
    )


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
