from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Any
import sqlite3, json, os, uuid, hashlib, secrets
from datetime import datetime

app = FastAPI()
DB = "nexus.db"

DIVISIONES = [
    "Telecomunicaciones y Sistemas Especiales",
    "HVAC",
    "IS Energy"
]

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            nombre TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS catalog (
            id TEXT PRIMARY KEY,
            division TEXT NOT NULL,
            sistema TEXT NOT NULL,
            desc TEXT NOT NULL,
            fab TEXT,
            precio REAL DEFAULT 0,
            unidad TEXT DEFAULT 'und',
            notas TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            division TEXT NOT NULL,
            nombre TEXT NOT NULL,
            cliente TEXT,
            elaborado TEXT,
            elaborado_user_id TEXT,
            fecha TEXT,
            params TEXT,
            solutions TEXT,
            total REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS sistemas (
            id TEXT PRIMARY KEY,
            division TEXT NOT NULL,
            nombre TEXT NOT NULL,
            color TEXT DEFAULT 'otro',
            es_default INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # Seed users
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        def make_user(email, nombre, admin):
            conn.execute(
                "INSERT INTO users (id,email,nombre,password_hash,is_admin) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), email, nombre,
                 hashlib.sha256("nexus2025".encode()).hexdigest(), admin)
            )
        make_user("admin@ingesoft.com",          "Administrador",    1)
        make_user("avieto@ingesoftcompany.com",  "Alexis Vieto",     1)
        conn.commit()

    # Seed sistemas per division
    if conn.execute("SELECT COUNT(*) FROM sistemas").fetchone()[0] == 0:
        tse_sistemas = [
            ("Alarma Contra Incendio","alarma"),
            ("Video Vigilancia","video"),
            ("Cableado Estructurado","cableado"),
            ("Control de Acceso","acceso"),
            ("Sonido Ambiental","sonido"),
            ("Telecomunicaciones","telecom"),
            ("Mantenimiento","mant"),
        ]
        hvac_sistemas = [
            ("Aire Acondicionado Split","video"),
            ("Aire Acondicionado Central","cableado"),
            ("Ventilación Mecánica","acceso"),
            ("Extracción de Humos","alarma"),
            ("Automatización HVAC","sonido"),
            ("Mantenimiento","mant"),
        ]
        energy_sistemas = [
            ("Paneles Solares","cableado"),
            ("Inversores","acceso"),
            ("Baterías y Almacenamiento","sonido"),
            ("Medición y Monitoreo","video"),
            ("Instalación Eléctrica","alarma"),
            ("Mantenimiento","mant"),
        ]
        for div, sistemas in [
            ("Telecomunicaciones y Sistemas Especiales", tse_sistemas),
            ("HVAC", hvac_sistemas),
            ("IS Energy", energy_sistemas),
        ]:
            for nombre, color in sistemas:
                conn.execute(
                    "INSERT INTO sistemas (id,division,nombre,color,es_default) VALUES (?,?,?,?,1)",
                    (str(uuid.uuid4()), div, nombre, color)
                )
        conn.commit()

    conn.close()

init_db()

# ── Models ────────────────────────────────────────────────────────────────────
class CatalogItem(BaseModel):
    id: Optional[str] = None
    division: Optional[str] = None
    sistema: str
    desc: str
    fab: Optional[str] = ""
    precio: float = 0
    unidad: Optional[str] = "und"
    notas: Optional[str] = ""

class Project(BaseModel):
    id: Optional[str] = None
    division: Optional[str] = None
    nombre: str
    cliente: Optional[str] = ""
    elaborado: Optional[str] = ""
    elaborado_user_id: Optional[str] = None
    fecha: Optional[str] = ""
    params: Optional[Any] = None
    solutions: Optional[Any] = None
    total: Optional[float] = 0

class SistemaItem(BaseModel):
    nombre: str
    color: Optional[str] = "otro"
    division: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class UserCreate(BaseModel):
    email: str
    nombre: str
    password: str
    is_admin: Optional[int] = 0

# ── AUTH ──────────────────────────────────────────────────────────────────────
def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

def get_current_user(request: Request):
    token = request.cookies.get("nx_session")
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    conn = get_db()
    row = conn.execute(
        "SELECT u.* FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token=?",
        (token,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Sesión inválida")
    return dict(row)

@app.post("/api/auth/login")
def login(data: LoginRequest, response: Response):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email=? AND password_hash=?",
        (data.email.strip().lower(), hash_pw(data.password))
    ).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions (token,user_id) VALUES (?,?)", (token, user['id']))
    conn.commit(); conn.close()
    # Session cookie — expires when browser closes (no max_age)
    response.set_cookie("nx_session", token, httponly=True, samesite="lax")
    return {"ok": True, "nombre": user['nombre'], "email": user['email'],
            "is_admin": user['is_admin'], "id": user['id']}

@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("nx_session")
    if token:
        conn = get_db()
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit(); conn.close()
    response.delete_cookie("nx_session")
    return {"ok": True}

@app.get("/api/auth/me")
def me(user=Depends(get_current_user)):
    return {"id": user['id'], "nombre": user['nombre'],
            "email": user['email'], "is_admin": user['is_admin']}

# ── USERS ─────────────────────────────────────────────────────────────────────
@app.get("/api/users")
def get_users(user=Depends(get_current_user)):
    if not user['is_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores")
    conn = get_db()
    rows = conn.execute(
        "SELECT id,email,nombre,is_admin,created_at FROM users ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/users")
def create_user(data: UserCreate, user=Depends(get_current_user)):
    if not user['is_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores pueden crear usuarios")
    conn = get_db()
    if conn.execute("SELECT id FROM users WHERE lower(email)=lower(?)", (data.email,)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Ya existe ese correo")
    uid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users (id,email,nombre,password_hash,is_admin) VALUES (?,?,?,?,?)",
        (uid, data.email.strip().lower(), data.nombre, hash_pw(data.password), data.is_admin)
    )
    conn.commit(); conn.close()
    return {"ok": True, "id": uid}

@app.delete("/api/users/{uid}")
def delete_user(uid: str, user=Depends(get_current_user)):
    if not user['is_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores")
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    conn.commit(); conn.close()
    return {"ok": True}

@app.put("/api/users/{uid}/password")
def change_password(uid: str, data: dict, user=Depends(get_current_user)):
    conn = get_db()
    conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                 (hash_pw(data['password']), uid))
    conn.commit(); conn.close()
    return {"ok": True}

# ── DIVISIONES ────────────────────────────────────────────────────────────────
@app.get("/api/divisiones")
def get_divisiones(user=Depends(get_current_user)):
    return DIVISIONES

# ── CATALOG ───────────────────────────────────────────────────────────────────
@app.get("/api/catalog")
def get_catalog(division: str, sistema: Optional[str]=None,
                q: Optional[str]=None, user=Depends(get_current_user)):
    conn = get_db()
    sql = "SELECT * FROM catalog WHERE division=?"
    args = [division]
    if sistema: sql += " AND sistema=?"; args.append(sistema)
    if q:
        sql += " AND (desc LIKE ? OR fab LIKE ? OR sistema LIKE ?)";
        args += [f"%{q}%"]*3
    sql += " ORDER BY sistema, desc"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/catalog")
def add_catalog(item: CatalogItem, user=Depends(get_current_user)):
    conn = get_db()
    item.id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO catalog (id,division,sistema,desc,fab,precio,unidad,notas) VALUES (?,?,?,?,?,?,?,?)",
        (item.id, item.division, item.sistema, item.desc,
         item.fab, item.precio, item.unidad, item.notas)
    )
    conn.commit(); conn.close()
    return item

@app.put("/api/catalog/{item_id}")
def update_catalog(item_id: str, item: CatalogItem, user=Depends(get_current_user)):
    conn = get_db()
    conn.execute(
        "UPDATE catalog SET sistema=?,desc=?,fab=?,precio=?,unidad=?,notas=? WHERE id=?",
        (item.sistema, item.desc, item.fab, item.precio,
         item.unidad, item.notas, item_id)
    )
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/catalog/{item_id}")
def delete_catalog(item_id: str, user=Depends(get_current_user)):
    conn = get_db()
    conn.execute("DELETE FROM catalog WHERE id=?", (item_id,))
    conn.commit(); conn.close()
    return {"ok": True}

@app.post("/api/catalog/bulk-add")
def bulk_add(items: List[CatalogItem], user=Depends(get_current_user)):
    conn = get_db()
    added = 0
    for item in items:
        exists = conn.execute(
            "SELECT id FROM catalog WHERE lower(desc)=lower(?) AND lower(fab)=lower(?) AND division=?",
            (item.desc, item.fab or '', item.division)
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO catalog (id,division,sistema,desc,fab,precio,unidad,notas) VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), item.division, item.sistema, item.desc,
                 item.fab or '', item.precio, item.unidad or 'und', 'Agregado desde proyecto')
            )
            added += 1
    conn.commit(); conn.close()
    return {"added": added}

# ── PROJECTS ──────────────────────────────────────────────────────────────────
@app.get("/api/projects")
def get_projects(division: str, user=Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM projects WHERE division=? ORDER BY updated_at DESC", (division,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['params']    = json.loads(d['params'])    if d['params']    else {}
        d['solutions'] = json.loads(d['solutions']) if d['solutions'] else []
        result.append(d)
    return result

@app.post("/api/projects")
def save_project(proj: Project, user=Depends(get_current_user)):
    conn = get_db()
    now = datetime.utcnow().isoformat()
    existing = conn.execute(
        "SELECT id, elaborado_user_id FROM projects WHERE nombre=? AND cliente=? AND division=?",
        (proj.nombre, proj.cliente, proj.division)
    ).fetchone()

    pid = existing['id'] if existing else str(uuid.uuid4())

    if existing:
        # Only creator can update
        if existing['elaborado_user_id'] and existing['elaborado_user_id'] != user['id']:
            conn.close()
            raise HTTPException(status_code=403,
                detail="Solo el creador puede editar este proyecto")
        conn.execute(
            "UPDATE projects SET elaborado=?,fecha=?,params=?,solutions=?,total=?,updated_at=? WHERE id=?",
            (proj.elaborado, proj.fecha, json.dumps(proj.params),
             json.dumps(proj.solutions), proj.total, now, pid)
        )
    else:
        conn.execute(
            "INSERT INTO projects (id,division,nombre,cliente,elaborado,elaborado_user_id,fecha,params,solutions,total,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, proj.division, proj.nombre, proj.cliente, proj.elaborado,
             user['id'], proj.fecha, json.dumps(proj.params),
             json.dumps(proj.solutions), proj.total, now, now)
        )
    conn.commit(); conn.close()
    return {"id": pid}

@app.delete("/api/projects/{proj_id}")
def delete_project(proj_id: str, user=Depends(get_current_user)):
    conn = get_db()
    proj = conn.execute(
        "SELECT elaborado_user_id FROM projects WHERE id=?", (proj_id,)
    ).fetchone()
    if proj and proj['elaborado_user_id'] and proj['elaborado_user_id'] != user['id']:
        if not user['is_admin']:
            conn.close()
            raise HTTPException(status_code=403, detail="Solo el creador puede eliminar este proyecto")
    conn.execute("DELETE FROM projects WHERE id=?", (proj_id,))
    conn.commit(); conn.close()
    return {"ok": True}

# ── SISTEMAS ──────────────────────────────────────────────────────────────────
@app.get("/api/sistemas")
def get_sistemas(division: str, user=Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM sistemas WHERE division=? ORDER BY es_default DESC, nombre",
        (division,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/sistemas")
def add_sistema(item: SistemaItem, user=Depends(get_current_user)):
    conn = get_db()
    if conn.execute(
        "SELECT id FROM sistemas WHERE lower(nombre)=lower(?) AND division=?",
        (item.nombre, item.division)
    ).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Ya existe esa categoría en esta división")
    sid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO sistemas (id,division,nombre,color,es_default) VALUES (?,?,?,?,0)",
        (sid, item.division, item.nombre.strip(), item.color)
    )
    conn.commit(); conn.close()
    return {"id": sid, "nombre": item.nombre, "color": item.color}

@app.delete("/api/sistemas/{sid}")
def delete_sistema(sid: str, user=Depends(get_current_user)):
    conn = get_db()
    row = conn.execute("SELECT es_default FROM sistemas WHERE id=?", (sid,)).fetchone()
    if row and row['es_default']:
        conn.close()
        raise HTTPException(status_code=400, detail="No se pueden eliminar categorías predeterminadas")
    conn.execute("DELETE FROM sistemas WHERE id=?", (sid,))
    conn.commit(); conn.close()
    return {"ok": True}

# ── FRONTEND ──────────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")
