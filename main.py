from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import secrets
import bcrypt

app = FastAPI()

# Session storage (in-memory, resets on restart)
sessions = {}

# API Models
class ProcessCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "normal"
    parent_id: Optional[int] = None
    assigned_to: Optional[int] = None

class ProcessUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[int] = None

class LoginData(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    email: str
    password: str
    password_confirm: str
    first_name: str
    last_name: str
    role: str = "user"

# Password validation
def validate_password(password: str) -> bool:
    if len(password) < 8:
        return False
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    return has_upper and has_lower and has_digit and has_special

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    password_confirm: Optional[str] = None
    role: Optional[str] = None

# Password hashing
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

# Auth check
def get_session(request: Request):
    session_id = request.cookies.get("session")
    if session_id and session_id in sessions:
        return sessions[session_id]
    return None

def require_auth(request: Request):
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session

def require_admin(request: Request):
    session = require_auth(request)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return session

# Database
def get_db():
    return psycopg2.connect(
        host="generic_db", port=5432, database="work_agent",
        user="admin", password="GenericDB2024!"
    )

# Logging
def log_login(user_id, email, action, success, ip_address):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO login_log (user_id, email, action, success, ip_address) VALUES (%s, %s, %s, %s, %s)",
        (user_id, email, action, success, ip_address)
    )
    conn.commit()
    conn.close()

# Auth Endpoints
@app.post("/api/login")
def login(data: LoginData, request: Request, response: Response):
    ip = request.client.host if request.client else None
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, username, password_hash, first_name, last_name, role FROM users WHERE username = %s", (data.email,))
    user = cur.fetchone()
    conn.close()

    if user and user["password_hash"] and verify_password(data.password, user["password_hash"]):
        session_id = secrets.token_hex(32)
        sessions[session_id] = {
            "user_id": user["id"],
            "email": user["username"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "role": user["role"]
        }
        response.set_cookie(key="session", value=session_id, httponly=True, samesite="strict")
        log_login(user["id"], data.email, "login", True, ip)
        return {"ok": True, "role": user["role"]}

    log_login(None, data.email, "login", False, ip)
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/api/logout")
def logout(request: Request, response: Response):
    session_id = request.cookies.get("session")
    ip = request.client.host if request.client else None
    if session_id and session_id in sessions:
        session = sessions[session_id]
        log_login(session.get("user_id"), session.get("email"), "logout", True, ip)
        del sessions[session_id]
    response.delete_cookie("session")
    return {"ok": True}

@app.get("/api/me")
def get_me(session: dict = Depends(require_auth)):
    return session

@app.get("/api/login-log")
def get_login_log(session: dict = Depends(require_admin)):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT l.id, l.email, l.action, l.success, l.ip_address, l.created_at,
               u.first_name, u.last_name
        FROM login_log l
        LEFT JOIN users u ON l.user_id = u.id
        ORDER BY l.created_at DESC
        LIMIT 100
    """)
    logs = cur.fetchall()
    conn.close()
    return logs

# User Management Endpoints
@app.get("/api/users")
def get_users(request: Request, session: dict = Depends(require_auth)):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    if session["role"] == "admin":
        cur.execute("SELECT id, username, first_name, last_name, role, created_at FROM users ORDER BY last_name, first_name")
    else:
        cur.execute("SELECT id, username, first_name, last_name, role, created_at FROM users WHERE id = %s", (session["user_id"],))

    users = cur.fetchall()
    conn.close()
    return users

@app.post("/api/users")
def create_user(data: UserCreate, session: dict = Depends(require_admin)):
    if data.password != data.password_confirm:
        raise HTTPException(status_code=400, detail="Passwörter stimmen nicht überein")

    if not validate_password(data.password):
        raise HTTPException(status_code=400, detail="Passwort erfüllt nicht die Anforderungen")

    conn = get_db()
    cur = conn.cursor()

    # Check if email exists
    cur.execute("SELECT id FROM users WHERE username = %s", (data.email,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="E-Mail existiert bereits")

    password_hash = hash_password(data.password)
    cur.execute(
        "INSERT INTO users (username, email, password_hash, first_name, last_name, role) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (data.email, data.email, password_hash, data.first_name, data.last_name, data.role)
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return {"id": new_id}

@app.put("/api/users/{user_id}")
def update_user(user_id: int, data: UserUpdate, request: Request, session: dict = Depends(require_auth)):
    # User can only update themselves, admin can update anyone
    if session["role"] != "admin" and session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    # Only admin can change roles
    if data.role and session["role"] != "admin":
        raise HTTPException(status_code=403, detail="Nur Admin kann Rollen ändern")

    # Password confirmation check
    if data.password:
        if data.password != data.password_confirm:
            raise HTTPException(status_code=400, detail="Passwörter stimmen nicht überein")
        if not validate_password(data.password):
            raise HTTPException(status_code=400, detail="Passwort erfüllt nicht die Anforderungen")

    conn = get_db()
    cur = conn.cursor()

    if data.first_name:
        cur.execute("UPDATE users SET first_name = %s, updated_at = %s WHERE id = %s", (data.first_name, datetime.now(), user_id))

    if data.last_name:
        cur.execute("UPDATE users SET last_name = %s, updated_at = %s WHERE id = %s", (data.last_name, datetime.now(), user_id))

    if data.password:
        password_hash = hash_password(data.password)
        cur.execute("UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s", (password_hash, datetime.now(), user_id))

    if data.role and session["role"] == "admin":
        cur.execute("UPDATE users SET role = %s, updated_at = %s WHERE id = %s", (data.role, datetime.now(), user_id))

    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, session: dict = Depends(require_admin)):
    if session["user_id"] == user_id:
        raise HTTPException(status_code=400, detail="Kann sich nicht selbst löschen")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

# Process Endpoints
@app.get("/api/processes")
def get_processes(request: Request, session: dict = Depends(require_auth)):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT p.id, p.title, p.description, p.status, p.priority,
               p.parent_id, p.assigned_to, p.created_by, p.created_at,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name
        FROM processes p
        LEFT JOIN users u ON p.assigned_to = u.id
        WHERE p.parent_id IS NULL
        ORDER BY
            CASE WHEN p.status = 'offen' THEN 1
                 WHEN p.status = 'wartend' THEN 2
                 ELSE 3 END,
            CASE WHEN p.priority = 'hoch' THEN 1
                 WHEN p.priority = 'normal' THEN 2
                 ELSE 3 END,
            p.title ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

@app.get("/api/processes/{process_id}")
def get_process(process_id: int, request: Request, session: dict = Depends(require_auth)):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Get main process
    cur.execute("""
        SELECT p.id, p.title, p.description, p.status, p.priority,
               p.parent_id, p.assigned_to, p.created_by, p.created_at,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name
        FROM processes p
        LEFT JOIN users u ON p.assigned_to = u.id
        WHERE p.id = %s
    """, (process_id,))
    process = cur.fetchone()
    if not process:
        conn.close()
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")

    # Get sub-processes
    cur.execute("""
        SELECT p.id, p.title, p.description, p.status, p.priority,
               p.assigned_to, p.created_at,
               u.first_name as assigned_first_name, u.last_name as assigned_last_name
        FROM processes p
        LEFT JOIN users u ON p.assigned_to = u.id
        WHERE p.parent_id = %s
        ORDER BY p.created_at ASC
    """, (process_id,))
    sub_processes = cur.fetchall()
    conn.close()

    process["sub_processes"] = sub_processes
    return process

@app.post("/api/processes")
def create_process(data: ProcessCreate, request: Request, session: dict = Depends(require_auth)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO processes (title, description, priority, parent_id, assigned_to, created_by)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (data.title, data.description, data.priority, data.parent_id, data.assigned_to, session["user_id"])
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return {"id": new_id}

@app.put("/api/processes/{process_id}")
def update_process(process_id: int, data: ProcessUpdate, request: Request, session: dict = Depends(require_auth)):
    conn = get_db()
    cur = conn.cursor()
    now = datetime.now()

    if data.title is not None:
        cur.execute(
            "UPDATE processes SET title = %s, updated_at = %s WHERE id = %s",
            (data.title, now, process_id)
        )

    if data.description is not None:
        cur.execute(
            "UPDATE processes SET description = %s, updated_at = %s WHERE id = %s",
            (data.description, now, process_id)
        )

    if data.status is not None:
        closed_at = now if data.status == 'geschlossen' else None
        cur.execute(
            "UPDATE processes SET status = %s, closed_at = %s, updated_at = %s WHERE id = %s",
            (data.status, closed_at, now, process_id)
        )

    if data.priority is not None:
        cur.execute(
            "UPDATE processes SET priority = %s, updated_at = %s WHERE id = %s",
            (data.priority, now, process_id)
        )

    if data.assigned_to is not None:
        # 0 means unassign
        assigned = data.assigned_to if data.assigned_to > 0 else None
        cur.execute(
            "UPDATE processes SET assigned_to = %s, updated_at = %s WHERE id = %s",
            (assigned, now, process_id)
        )

    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/processes/{process_id}")
def delete_process(process_id: int, request: Request, session: dict = Depends(require_auth)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM processes WHERE id = %s", (process_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pages - mit no-cache headers
def html_response(content: str):
    return HTMLResponse(
        content=content,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    )

@app.get("/login", response_class=HTMLResponse)
def login_page():
    with open("static/login.html") as f:
        return html_response(f.read())

@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    if not get_session(request):
        return RedirectResponse(url="/login", status_code=302)
    with open("static/users.html") as f:
        return html_response(f.read())

@app.get("/log", response_class=HTMLResponse)
def log_page(request: Request):
    if not get_session(request):
        return RedirectResponse(url="/login", status_code=302)
    with open("static/log.html") as f:
        return html_response(f.read())

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if not get_session(request):
        return RedirectResponse(url="/login", status_code=302)
    with open("static/index.html") as f:
        return html_response(f.read())
