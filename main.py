from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Any
import sqlite3, json, os, uuid
from datetime import datetime

app = FastAPI()
DB = "nexus.db"

# ── Init DB ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS catalog (
            id TEXT PRIMARY KEY,
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
            nombre TEXT NOT NULL,
            cliente TEXT,
            elaborado TEXT,
            fecha TEXT,
            params TEXT,
            solutions TEXT,
            total REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # Seed catalog if empty
    count = conn.execute("SELECT COUNT(*) FROM catalog").fetchone()[0]
    if count == 0:
        seed = [
            ("Alarma Contra Incendio","Panel de Control Direccionable 2 lazos","Notifier NFS2-3030",1850.00,"und"),
            ("Alarma Contra Incendio","Detector de Humo Direccionable","System Sensor D4120",87.50,"und"),
            ("Alarma Contra Incendio","Detector Multicriterio Direccionable","System Sensor OSHSD",94.75,"und"),
            ("Alarma Contra Incendio","Estación Manual Doble Acción","System Sensor 2099-9754",122.18,"und"),
            ("Alarma Contra Incendio","Módulo Aislador de Corto Circuito","Notifier MMX-1",79.40,"und"),
            ("Alarma Contra Incendio","Sirena Audible","Wheelock NS-12/24-R",88.08,"und"),
            ("Alarma Contra Incendio","Sirena con Luz Estroboscópica Interior","Wheelock E50-24MCW-FR",114.19,"und"),
            ("Alarma Contra Incendio","Sirena con Luz Estroboscópica Exterior","Wheelock WH-400-R",176.89,"und"),
            ("Alarma Contra Incendio","Base estándar para detector","System Sensor B501",20.36,"und"),
            ("Alarma Contra Incendio","Detector en ducto de aire","System Sensor FAPT851",201.38,"und"),
            ("Alarma Contra Incendio","Módulo de control HVAC","Notifier FCM-1",158.81,"und"),
            ("Alarma Contra Incendio","Módulo de Monitoreo de contacto Seco","Notifier FMM-1",94.84,"und"),
            ("Alarma Contra Incendio","Panel de evacuación por Voz","Notifier NCA-2",5100.72,"und"),
            ("Alarma Contra Incendio","Batería de respaldo 12v 12Ah","Power-Sonic PS-12120",26.75,"und"),
            ("Alarma Contra Incendio","Rollo 1000 Pies #18/2 Shield (SLC)","Belden 5220UE",132.75,"rollo"),
            ("Alarma Contra Incendio","Rollo 1000 Pies #16/2 Notificación","Belden 5320UE",165.85,"rollo"),
            ("Video Vigilancia","Cámara Domo IP 4MP Lente Fijo 2.8mm","Hikvision DS-2CD2143G2-I",145.00,"und"),
            ("Video Vigilancia","Cámara Exterior IP 4MP Varifocal 2.8-9mm","Hikvision DS-2CD2T43G2-4I",225.00,"und"),
            ("Video Vigilancia","Cámara PTZ IP 4MP 25x Zoom","Hikvision DS-2DE4425IWG-E",780.00,"und"),
            ("Video Vigilancia","NVR 32 canales 4K","Hikvision DS-7732NI-I4/16P",1250.00,"und"),
            ("Video Vigilancia","NVR 16 canales 4K","Hikvision DS-7716NI-I4/16P",850.00,"und"),
            ("Video Vigilancia","Disco Duro 4TB Surveillance","Seagate SkyHawk ST4000VX016",95.00,"und"),
            ("Video Vigilancia","Switch PoE 16 puertos","TP-Link TL-SG1016PE",185.00,"und"),
            ("Video Vigilancia","Monitor LED 32\" Full HD","LG 32MN500M-B",285.00,"und"),
            ("Cableado Estructurado","Cable Cat 6A UTP CMP Azul (caja 305m)","Panduit PUP6X04BU-EI",185.00,"caja"),
            ("Cableado Estructurado","Jack Modular Cat 6A UTP","Panduit CJ6X88TGBU",12.50,"und"),
            ("Cableado Estructurado","Placa frontal 1 puerto","Panduit CFPE1IW",4.20,"und"),
            ("Cableado Estructurado","Patch Panel 48 puertos Cat 6A","Panduit DP6X48TGY",285.00,"und"),
            ("Cableado Estructurado","Rack 42U 600x1000","APC AR3100",950.00,"und"),
            ("Cableado Estructurado","UPS 3kVA Torre","APC SMT3000I",1450.00,"und"),
            ("Control de Acceso","Lector Prox tarjeta HID 125kHz","HID ProxPoint 6005",95.00,"und"),
            ("Control de Acceso","Cerradura Magnética 600lbs","Seco-Larm SM-562L-AQ",95.00,"und"),
            ("Control de Acceso","Tarjeta de proximidad HID","HID 1326 ProxCard II",4.50,"und"),
            ("Sonido Ambiental","Amplificador 2x350W","QSC CX-Q2K4",1850.00,"und"),
            ("Sonido Ambiental","Bocina para cielo 6\" 8W","QSC AcousticDesign AD-C6T",195.00,"und"),
            ("Sonido Ambiental","Procesador de audio DSP","QSC Core 110F",2800.00,"und"),
            ("Sonido Ambiental","Cable de audio #14awg (rollo 300m)","Belden 5200UL",473.56,"rollo"),
        ]
        for sistema, desc, fab, precio, unidad in seed:
            conn.execute(
                "INSERT INTO catalog (id,sistema,desc,fab,precio,unidad,notas) VALUES (?,?,?,?,?,?,'')",
                (str(uuid.uuid4()), sistema, desc, fab, precio, unidad)
            )
        conn.commit()
    conn.close()

init_db()

# ── Models ───────────────────────────────────────────────────────────────────
class CatalogItem(BaseModel):
    id: Optional[str] = None
    sistema: str
    desc: str
    fab: Optional[str] = ""
    precio: float = 0
    unidad: Optional[str] = "und"
    notas: Optional[str] = ""

class Project(BaseModel):
    id: Optional[str] = None
    nombre: str
    cliente: Optional[str] = ""
    elaborado: Optional[str] = ""
    fecha: Optional[str] = ""
    params: Optional[Any] = None
    solutions: Optional[Any] = None
    total: Optional[float] = 0

# ── CATALOG endpoints ─────────────────────────────────────────────────────────
@app.get("/api/catalog")
def get_catalog(sistema: Optional[str] = None, q: Optional[str] = None):
    conn = get_db()
    sql = "SELECT * FROM catalog WHERE 1=1"
    args = []
    if sistema:
        sql += " AND sistema=?"; args.append(sistema)
    if q:
        sql += " AND (desc LIKE ? OR fab LIKE ? OR sistema LIKE ?)"; args += [f"%{q}%"]*3
    sql += " ORDER BY sistema, desc"
    rows = conn.execute(sql, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/catalog")
def add_catalog(item: CatalogItem):
    conn = get_db()
    item.id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO catalog (id,sistema,desc,fab,precio,unidad,notas) VALUES (?,?,?,?,?,?,?)",
        (item.id, item.sistema, item.desc, item.fab, item.precio, item.unidad, item.notas)
    )
    conn.commit(); conn.close()
    return item

@app.put("/api/catalog/{item_id}")
def update_catalog(item_id: str, item: CatalogItem):
    conn = get_db()
    conn.execute(
        "UPDATE catalog SET sistema=?,desc=?,fab=?,precio=?,unidad=?,notas=? WHERE id=?",
        (item.sistema, item.desc, item.fab, item.precio, item.unidad, item.notas, item_id)
    )
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/catalog/{item_id}")
def delete_catalog(item_id: str):
    conn = get_db()
    conn.execute("DELETE FROM catalog WHERE id=?", (item_id,))
    conn.commit(); conn.close()
    return {"ok": True}

# ── PROJECTS endpoints ────────────────────────────────────────────────────────
@app.get("/api/projects")
def get_projects():
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['params']    = json.loads(d['params'])    if d['params']    else {}
        d['solutions'] = json.loads(d['solutions']) if d['solutions'] else []
        result.append(d)
    return result

@app.post("/api/projects")
def save_project(proj: Project):
    conn = get_db()
    now = datetime.utcnow().isoformat()
    existing = conn.execute(
        "SELECT id FROM projects WHERE nombre=? AND cliente=?",
        (proj.nombre, proj.cliente)
    ).fetchone()
    pid = existing['id'] if existing else str(uuid.uuid4())
    if existing:
        conn.execute(
            "UPDATE projects SET elaborado=?,fecha=?,params=?,solutions=?,total=?,updated_at=? WHERE id=?",
            (proj.elaborado, proj.fecha, json.dumps(proj.params), json.dumps(proj.solutions), proj.total, now, pid)
        )
    else:
        conn.execute(
            "INSERT INTO projects (id,nombre,cliente,elaborado,fecha,params,solutions,total,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid, proj.nombre, proj.cliente, proj.elaborado, proj.fecha,
             json.dumps(proj.params), json.dumps(proj.solutions), proj.total, now, now)
        )
    conn.commit(); conn.close()
    return {"id": pid}

@app.delete("/api/projects/{proj_id}")
def delete_project(proj_id: str):
    conn = get_db()
    conn.execute("DELETE FROM projects WHERE id=?", (proj_id,))
    conn.commit(); conn.close()
    return {"ok": True}

# ── Auto-add new catalog items from project ───────────────────────────────────
@app.post("/api/catalog/bulk-add")
def bulk_add(items: List[CatalogItem]):
    conn = get_db()
    added = 0
    for item in items:
        exists = conn.execute(
            "SELECT id FROM catalog WHERE lower(desc)=lower(?) AND lower(fab)=lower(?)",
            (item.desc, item.fab or '')
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO catalog (id,sistema,desc,fab,precio,unidad,notas) VALUES (?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), item.sistema, item.desc, item.fab or '',
                 item.precio, item.unidad or 'und', 'Agregado desde proyecto')
            )
            added += 1
    conn.commit(); conn.close()
    return {"added": added}

# ── Serve frontend ────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")
