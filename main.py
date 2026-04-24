from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Any
import json, os, uuid, hashlib, secrets
from datetime import datetime

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    def get_db():
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    PH = "%s"  # PostgreSQL placeholder
else:
    import sqlite3
    def get_db():
        conn = sqlite3.connect("nexus.db")
        conn.row_factory = sqlite3.Row
        return conn
    PH = "?"   # SQLite placeholder

app = FastAPI()

DIVISIONES = [
    "Telecomunicaciones y Sistemas Especiales",
    "HVAC",
    "IS Energy"
]

def init_db():
    conn = get_db()
    cur = conn.cursor()

    if DATABASE_URL:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (now()::text)
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                created_at TEXT DEFAULT (now()::text)
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS catalog (
                id TEXT PRIMARY KEY,
                division TEXT NOT NULL,
                sistema TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                fab TEXT,
                precio REAL DEFAULT 0,
                unidad TEXT DEFAULT 'und',
                notas TEXT,
                created_at TEXT DEFAULT (now()::text)
            )""")
        cur.execute("""
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
                created_at TEXT DEFAULT (now()::text),
                updated_at TEXT DEFAULT (now()::text)
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sistemas (
                id TEXT PRIMARY KEY,
                division TEXT NOT NULL,
                nombre TEXT NOT NULL,
                color TEXT DEFAULT 'otro',
                es_default INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (now()::text)
            )""")
    else:
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL, password_hash TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS catalog (
                id TEXT PRIMARY KEY, division TEXT NOT NULL, sistema TEXT NOT NULL,
                descripcion TEXT NOT NULL, fab TEXT, precio REAL DEFAULT 0,
                unidad TEXT DEFAULT 'und', notas TEXT, created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, division TEXT NOT NULL, nombre TEXT NOT NULL,
                cliente TEXT, elaborado TEXT, elaborado_user_id TEXT, fecha TEXT,
                params TEXT, solutions TEXT, total REAL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sistemas (
                id TEXT PRIMARY KEY, division TEXT NOT NULL, nombre TEXT NOT NULL,
                color TEXT DEFAULT 'otro', es_default INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
    conn.commit()

    # Seed users
    cur.execute(f"SELECT COUNT(*) FROM users")
    count = list(cur.fetchone().values())[0] if DATABASE_URL else cur.fetchone()[0]
    if count == 0:
        def make_user(email, nombre, admin):
            cur.execute(
                f"INSERT INTO users (id,email,nombre,password_hash,is_admin) VALUES ({PH},{PH},{PH},{PH},{PH})",
                (str(uuid.uuid4()), email, nombre,
                 hashlib.sha256("nexus2025".encode()).hexdigest(), admin)
            )
        make_user("admin@ingesoft.com", "Administrador", 1)
        make_user("avieto@ingesoftcompany.com", "Alexis Vieto", 1)
        conn.commit()

    # Seed sistemas
    cur.execute("SELECT COUNT(*) FROM sistemas")
    sis_count = list(cur.fetchone().values())[0] if DATABASE_URL else cur.fetchone()[0]
    if sis_count == 0:
        all_sistemas = [
            ("Telecomunicaciones y Sistemas Especiales", "Alarma Contra Incendio", "alarma"),
            ("Telecomunicaciones y Sistemas Especiales", "Video Vigilancia", "video"),
            ("Telecomunicaciones y Sistemas Especiales", "Cableado Estructurado", "cableado"),
            ("Telecomunicaciones y Sistemas Especiales", "Control de Acceso", "acceso"),
            ("Telecomunicaciones y Sistemas Especiales", "Sonido Ambiental", "sonido"),
            ("Telecomunicaciones y Sistemas Especiales", "Telecomunicaciones", "telecom"),
            ("Telecomunicaciones y Sistemas Especiales", "Mantenimiento", "mant"),
            ("HVAC", "Aire Acondicionado Split", "video"),
            ("HVAC", "Aire Acondicionado Central", "cableado"),
            ("HVAC", "Ventilación Mecánica", "acceso"),
            ("HVAC", "Extracción de Humos", "alarma"),
            ("HVAC", "Automatización HVAC", "sonido"),
            ("HVAC", "Mantenimiento", "mant"),
            ("IS Energy", "Paneles Solares", "cableado"),
            ("IS Energy", "Inversores", "acceso"),
            ("IS Energy", "Baterías y Almacenamiento", "sonido"),
            ("IS Energy", "Medición y Monitoreo", "video"),
            ("IS Energy", "Instalación Eléctrica", "alarma"),
            ("IS Energy", "Mantenimiento", "mant"),
        ]
        for div, nombre, color in all_sistemas:
            cur.execute(
                f"INSERT INTO sistemas (id,division,nombre,color,es_default) VALUES ({PH},{PH},{PH},{PH},1)",
                (str(uuid.uuid4()), div, nombre, color)
            )
        conn.commit()

    cur.close()
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

def row_to_dict(row):
    if row is None: return None
    if DATABASE_URL: return dict(row)
    return dict(row)

def rows_to_list(rows):
    return [dict(r) for r in rows]

def get_current_user(request: Request):
    token = request.cookies.get("nx_session")
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        f"SELECT u.* FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token={PH}",
        (token,)
    )
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Sesión inválida")
    return dict(row)

@app.post("/api/auth/login")
def login(data: LoginRequest, response: Response):
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        f"SELECT * FROM users WHERE email={PH} AND password_hash={PH}",
        (data.email.strip().lower(), hash_pw(data.password))
    )
    user = cur.fetchone()
    if not user:
        cur.close(); conn.close()
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    token = secrets.token_urlsafe(32)
    cur.execute(f"INSERT INTO sessions (token,user_id) VALUES ({PH},{PH})", (token, user['id']))
    conn.commit(); cur.close(); conn.close()
    response.set_cookie("nx_session", token, httponly=True, samesite="lax")
    return {"ok": True, "id": user['id'], "nombre": user['nombre'],
            "email": user['email'], "is_admin": user['is_admin']}

@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("nx_session")
    if token:
        conn = get_db(); cur = conn.cursor()
        cur.execute(f"DELETE FROM sessions WHERE token={PH}", (token,))
        conn.commit(); cur.close(); conn.close()
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
    conn = get_db(); cur = conn.cursor()
    cur.execute("SELECT id,email,nombre,is_admin,created_at FROM users ORDER BY created_at")
    rows = rows_to_list(cur.fetchall())
    cur.close(); conn.close()
    return rows

@app.post("/api/users")
def create_user(data: UserCreate, user=Depends(get_current_user)):
    if not user['is_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores")
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT id FROM users WHERE lower(email)=lower({PH})", (data.email,))
    if cur.fetchone():
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="Ya existe ese correo")
    uid = str(uuid.uuid4())
    cur.execute(
        f"INSERT INTO users (id,email,nombre,password_hash,is_admin) VALUES ({PH},{PH},{PH},{PH},{PH})",
        (uid, data.email.strip().lower(), data.nombre, hash_pw(data.password), data.is_admin)
    )
    conn.commit(); cur.close(); conn.close()
    return {"ok": True, "id": uid}

@app.delete("/api/users/{uid}")
def delete_user(uid: str, user=Depends(get_current_user)):
    if not user['is_admin']:
        raise HTTPException(status_code=403, detail="Solo administradores")
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"DELETE FROM users WHERE id={PH}", (uid,))
    cur.execute(f"DELETE FROM sessions WHERE user_id={PH}", (uid,))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}

# ── DIVISIONES ────────────────────────────────────────────────────────────────
@app.get("/api/divisiones")
def get_divisiones(user=Depends(get_current_user)):
    return DIVISIONES

# ── CATALOG ───────────────────────────────────────────────────────────────────
@app.get("/api/catalog")
def get_catalog(division: str, sistema: Optional[str]=None,
                q: Optional[str]=None, user=Depends(get_current_user)):
    conn = get_db(); cur = conn.cursor()
    sql = f"SELECT id,division,sistema,descripcion as desc,fab,precio,unidad,notas FROM catalog WHERE division={PH}"
    args = [division]
    if sistema: sql += f" AND sistema={PH}"; args.append(sistema)
    if q:
        sql += f" AND (desc LIKE {PH} OR fab LIKE {PH} OR sistema LIKE {PH})"
        args += [f"%{q}%"]*3
    sql += " ORDER BY sistema, descripcion"
    cur.execute(sql, args)
    rows = rows_to_list(cur.fetchall())
    cur.close(); conn.close()
    return rows

@app.post("/api/catalog")
def add_catalog(item: CatalogItem, user=Depends(get_current_user)):
    conn = get_db(); cur = conn.cursor()
    item.id = str(uuid.uuid4())
    cur.execute(
        f"INSERT INTO catalog (id,division,sistema,descripcion,fab,precio,unidad,notas) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
        (item.id, item.division, item.sistema, item.desc, item.fab, item.precio, item.unidad, item.notas)
    )
    conn.commit(); cur.close(); conn.close()
    return item

@app.put("/api/catalog/{item_id}")
def update_catalog(item_id: str, item: CatalogItem, user=Depends(get_current_user)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        f"UPDATE catalog SET sistema={PH},descripcion={PH},fab={PH},precio={PH},unidad={PH},notas={PH} WHERE id={PH}",
        (item.sistema, item.desc, item.fab, item.precio, item.unidad, item.notas, item_id)
    )
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}

@app.delete("/api/catalog/{item_id}")
def delete_catalog(item_id: str, user=Depends(get_current_user)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"DELETE FROM catalog WHERE id={PH}", (item_id,))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}

@app.post("/api/catalog/bulk-add")
def bulk_add(items: List[CatalogItem], user=Depends(get_current_user)):
    conn = get_db(); cur = conn.cursor()
    added = 0
    for item in items:
        cur.execute(
            f"SELECT id FROM catalog WHERE lower(descripcion)=lower({PH}) AND lower(fab)=lower({PH}) AND division={PH}",
            (item.desc, item.fab or '', item.division)
        )
        if not cur.fetchone():
            cur.execute(
                f"INSERT INTO catalog (id,division,sistema,descripcion,fab,precio,unidad,notas) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
                (str(uuid.uuid4()), item.division, item.sistema, item.desc,
                 item.fab or '', item.precio, item.unidad or 'und', 'Agregado desde proyecto')
            )
            added += 1
    conn.commit(); cur.close(); conn.close()
    return {"added": added}

# ── PROJECTS ──────────────────────────────────────────────────────────────────
@app.get("/api/projects")
def get_projects(division: str, user=Depends(get_current_user)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT * FROM projects WHERE division={PH} ORDER BY updated_at DESC", (division,))
    result = []
    for r in cur.fetchall():
        d = dict(r)
        d['params']    = json.loads(d['params'])    if d['params']    else {}
        d['solutions'] = json.loads(d['solutions']) if d['solutions'] else []
        result.append(d)
    cur.close(); conn.close()
    return result

@app.post("/api/projects")
def save_project(proj: Project, user=Depends(get_current_user)):
    conn = get_db(); cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute(
        f"SELECT id, elaborado_user_id FROM projects WHERE nombre={PH} AND cliente={PH} AND division={PH}",
        (proj.nombre, proj.cliente, proj.division)
    )
    existing = cur.fetchone()
    pid = dict(existing)['id'] if existing else str(uuid.uuid4())
    if existing:
        ex = dict(existing)
        if ex['elaborado_user_id'] and ex['elaborado_user_id'] != user['id'] and not user['is_admin']:
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Solo el creador puede editar este proyecto")
        cur.execute(
            f"UPDATE projects SET elaborado={PH},fecha={PH},params={PH},solutions={PH},total={PH},updated_at={PH} WHERE id={PH}",
            (proj.elaborado, proj.fecha, json.dumps(proj.params),
             json.dumps(proj.solutions), proj.total, now, pid)
        )
    else:
        cur.execute(
            f"INSERT INTO projects (id,division,nombre,cliente,elaborado,elaborado_user_id,fecha,params,solutions,total,created_at,updated_at) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
            (pid, proj.division, proj.nombre, proj.cliente, proj.elaborado,
             user['id'], proj.fecha, json.dumps(proj.params),
             json.dumps(proj.solutions), proj.total, now, now)
        )
    conn.commit(); cur.close(); conn.close()
    return {"id": pid}

@app.delete("/api/projects/{proj_id}")
def delete_project(proj_id: str, user=Depends(get_current_user)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT elaborado_user_id FROM projects WHERE id={PH}", (proj_id,))
    proj = cur.fetchone()
    if proj:
        p = dict(proj)
        if p['elaborado_user_id'] and p['elaborado_user_id'] != user['id'] and not user['is_admin']:
            cur.close(); conn.close()
            raise HTTPException(status_code=403, detail="Solo el creador o un admin puede eliminar este proyecto")
    cur.execute(f"DELETE FROM projects WHERE id={PH}", (proj_id,))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}

# ── SISTEMAS ──────────────────────────────────────────────────────────────────
@app.get("/api/sistemas")
def get_sistemas(division: str, user=Depends(get_current_user)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        f"SELECT * FROM sistemas WHERE division={PH} ORDER BY es_default DESC, nombre", (division,)
    )
    rows = rows_to_list(cur.fetchall())
    cur.close(); conn.close()
    return rows

@app.post("/api/sistemas")
def add_sistema(item: SistemaItem, user=Depends(get_current_user)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(
        f"SELECT id FROM sistemas WHERE lower(nombre)=lower({PH}) AND division={PH}",
        (item.nombre, item.division)
    )
    if cur.fetchone():
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="Ya existe esa categoría en esta división")
    sid = str(uuid.uuid4())
    cur.execute(
        f"INSERT INTO sistemas (id,division,nombre,color,es_default) VALUES ({PH},{PH},{PH},{PH},0)",
        (sid, item.division, item.nombre.strip(), item.color)
    )
    conn.commit(); cur.close(); conn.close()
    return {"id": sid, "nombre": item.nombre, "color": item.color}

@app.delete("/api/sistemas/{sid}")
def delete_sistema(sid: str, user=Depends(get_current_user)):
    conn = get_db(); cur = conn.cursor()
    cur.execute(f"SELECT es_default FROM sistemas WHERE id={PH}", (sid,))
    row = cur.fetchone()
    if row and dict(row)['es_default']:
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="No se pueden eliminar categorías predeterminadas")
    cur.execute(f"DELETE FROM sistemas WHERE id={PH}", (sid,))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}

# ── FRONTEND ──────────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")