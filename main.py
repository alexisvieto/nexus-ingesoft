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

# Ensure static directory exists
import pathlib
pathlib.Path("static").mkdir(exist_ok=True)

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
            ("HVAC", "Aire Acondicionado VRF / Multi V", "video"),
            ("HVAC", "Aire Acondicionado Multi Split", "cableado"),
            ("HVAC", "Aire Acondicionado Single Split", "acceso"),
            ("HVAC", "Ductos y Manejadoras de Aire", "sonido"),
            ("HVAC", "Ventilación y Extracción", "telecom"),
            ("HVAC", "Automatización y Control HVAC", "alarma"),
            ("HVAC", "Sistemas de Agua Helada (Chiller)", "mant"),
            ("HVAC", "Accesorios HVAC", "otro"),
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

    # Seed HVAC catalog
    cur.execute(f"SELECT COUNT(*) FROM catalog WHERE division={PH}", ('HVAC',))
    hvac_count = list(cur.fetchone().values())[0] if DATABASE_URL else cur.fetchone()[0]
    if hvac_count == 0:
        hvac_items = [['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (220V) | ARUV096BTE5.AWGBLAT', 'LG', 5748.38, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (220V) | ARUV121BTE5.AWGBLAT', 'LG', 5829.47, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (220V) | ARUV144BTE5.AWGBLAT', 'LG', 6126.8, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (220V) | ARUV168BTE5.AWGBLAT', 'LG', 7721.57, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (220V) | ARUV192BTE5.AWGBLAT', 'LG', 8856.83, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (220V) | ARUV216BTE5.AWGBLAT', 'LG', 9343.37, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (220V) | ARUV241BTE5.AWGBLAT', 'LG', 9838.92, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (220V) | ARUV264BTE5.AWGBLAT', 'LG', 10839.03, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (460V) | ARUV096DTE5.AWGBLAT', 'LG', 5748.38, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (460V) | ARUV121DTE5.AWGBLAT', 'LG', 5829.47, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (460V) | ARUV144DTE5.AWGBLAT', 'LG', 6126.8, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (460V) | ARUV168DTE5.AWGBLAT', 'LG', 7721.57, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (460V) | ARUV192DTE5.AWGBLAT', 'LG', 8856.83, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (460V) | ARUV216DTE5.AWGBLAT', 'LG', 9343.37, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (460V) | ARUV241DTE5.AWGBLAT', 'LG', 9838.92, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 (460V) | ARUV264DTE5.AWGBLAT', 'LG', 10839.03, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (220V) | ARUM072BTE5.AWGBLUS', 'LG', 6135.81, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (220V) | ARUM096BTE5.AWGBLUS', 'LG', 7162.95, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (220V) | ARUM121BTE5.AWGBLUS', 'LG', 7388.2, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (220V) | ARUM144BTE5.AWGBLUS', 'LG', 8658.61, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (220V) | ARUM168BTE5.AWGBLUS', 'LG', 9253.27, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (220V) | ARUM192BTE5.AWGBLUS', 'LG', 9775.85, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (220V) | ARUM216BTE5.AWGBLUS', 'LG', 11010.22, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (220V) | ARUM241BTE5.AWGBLUS', 'LG', 12028.35, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (460V) | ARUM072DTE5.AWGBLUS', 'LG', 6135.81, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (460V) | ARUM096DTE5.AWGBLUS', 'LG', 7162.95, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (460V) | ARUM121DTE5.AWGBLUS', 'LG', 7388.2, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (460V) | ARUM144DTE5.AWGBLUS', 'LG', 8658.61, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (460V) | ARUM168DTE5.AWGBLUS', 'LG', 9253.27, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (460V) | ARUM192DTE5.AWGBLUS', 'LG', 9775.85, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (460V) | ARUM216DTE5.AWGBLUS', 'LG', 11010.22, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/R (460V) | ARUM241DTE5.AWGBLUS', 'LG', 12028.35, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S (1 Fan R1 comp) | ARUV040GSD5.AWGBLAT', 'LG', 1756.95, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S (1 Fan R1 comp) | ARUV050GSD5.AWGBLAT', 'LG', 2027.25, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S (1 Fan R1 comp) | ARUV060GSD5.AWGBLAT', 'LG', 2297.55, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S (1 Fan) | ARUN040GSS5.AWGBLAT', 'LG', 2450.72, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S (1 Fan R1 comp) | ARUN050GSS5.AWGBLAT', 'LG', 2585.87, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S (1 Fan R1 comp) | ARUN060GSS5.AWGBLAT', 'LG', 2721.02, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S | ARUN080BSS0.AWGBLAT', 'LG', 3829.25, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S | ARUN100BSS0.AWGBLAT', 'LG', 4712.23, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S | ARUN120BSS0.AWGBLAT', 'LG', 5045.6, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S (China) | ARUN040GSS1.EWGTLAT', 'LG', 2252.5, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S (China) | ARUN050GSS1.EWGTLAT', 'LG', 2432.7, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S (China) | ARUN060GSS1.EWGTLAT', 'LG', 2522.8, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (220V) 6 ton | ARWM072BAS5.AWGBLUS', 'LG', 6757.5, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (220V) 8 ton | ARWM096BAS5.AWGBLUS', 'LG', 7298.1, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (220V) 10 ton | ARWM121BAS5.AWGBLUS', 'LG', 7838.7, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (220V) 12 ton | ARWM144BAS5.AWGBLUS', 'LG', 8379.3, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) 6 ton | ARWM072DAS5.AWGBLUS', 'LG', 6757.5, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) 8 ton | ARWM096DAS5.AWGBLUS', 'LG', 7298.1, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) 10 ton | ARWM121DAS5.AWGBLUS', 'LG', 7838.7, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) 12 ton | ARWM144DAS5.AWGBLUS', 'LG', 8379.3, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) 14 ton | ARWM168DAS5.AWGBLUS', 'LG', 8919.9, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) 16 ton | ARWM192DAS5.AWGBLUS', 'LG', 9460.5, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/P (220V) | ARUN100BTE5.AWGBBRZ', 'LG', 5973.63, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/P (220V) | ARUN120BTE5.AWGBBRZ', 'LG', 6072.74, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/P (220V) | ARUN140BTE5.AWGBBRZ', 'LG', 6370.07, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/P (220V) | ARUN160BTE5.AWGBBRZ', 'LG', 8036.92, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/P (220V) | ARUN180BTE5.AWGBBRZ', 'LG', 9217.23, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/P (220V) | ARUN200BTE5.AWGBBRZ', 'LG', 9712.78, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/P (220V) | ARUN220BTE5.AWGBBRZ', 'LG', 10235.36, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/P (220V) | ARUN240BTE5.AWGBBRZ', 'LG', 11271.51, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V 5 H/P (220V) | ARUN260BTE5.AWGBBRZ', 'LG', 12226.57, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC (+Wifi) | ARNU05GSJN4.AMBBLAT', 'LG', 369.41, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC (+Wifi) | ARNU07GSJN4.AMBBLAT', 'LG', 378.42, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC (+Wifi) | ARNU09GSJN4.AMBBLAT', 'LG', 405.45, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC (+Wifi) | ARNU12GSJN4.AMBBLAT', 'LG', 423.47, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC (+Wifi) | ARNU15GSJN4.AMBBLAT', 'LG', 441.49, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC (+Wifi) | ARNU18GSKN4.AMBBLAT', 'LG', 513.57, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC (+Wifi) | ARNU24GSKN4.AMBBLAT', 'LG', 540.6, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC (+Wifi) | ARNU30GSVA4.AMBBLAT', 'LG', 639.71, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC (+Wifi) | ARNU36GSVA4.AMBBLAT', 'LG', 711.79, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool (+Wifi) | ARNU05GSJR4.AMBBLAT', 'LG', 450.5, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool (+Wifi) | ARNU07GSJR4.AMBBLAT', 'LG', 495.55, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool (+Wifi) | ARNU09GSJR4.AMBBLAT', 'LG', 486.54, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool (+Wifi) | ARNU12GSJR4.AMBBLAT', 'LG', 513.57, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool (+Wifi) | ARNU15GSJR4.AMBBLAT', 'LG', 531.59, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool (+Wifi) | ARNU18GSKR4.AMBBLAT', 'LG', 612.68, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool (+Wifi) | ARNU24GSKR4.AMBBLAT', 'LG', 657.73, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool Gallery (+Wifi) | ARNU07GSF14.ENCALEU', 'LG', 531.59, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool Gallery (+Wifi) | ARNU09GSF14.ENCALEU', 'LG', 558.62, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool Gallery (+Wifi) | ARNU12GSF14.ENCALEU', 'LG', 603.67, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 1way (+Wifi / non Plasma) | ARNU07GTUB4.ANWBLAT', 'LG', 432.48, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 1way (+Wifi / non Plasma) | ARNU09GTUB4.ANWBLAT', 'LG', 468.52, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 1way (+Wifi / non Plasma) | ARNU12GTUB4.ANWBLAT', 'LG', 504.56, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Zone Controller | ABZCA.ENCXLEU', 'LG', 40.55, 'und'], ['HVAC', 'Accesorios HVAC', 'CO2 Sensor | AHCS100H0.ENCXLEU', 'LG', 99.11, 'und'], ['HVAC', 'Accesorios HVAC', 'HEADER BRANCH / 4 BRANCH | ARBL054.ENCXCOM', 'LG', 72.08, 'und'], ['HVAC', 'Accesorios HVAC', 'HEADER BRANCH / 7 BRANCH | ARBL057.ENCXCOM', 'LG', 117.13, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 1way (+Wifi / non Plasma) | ARNU18GTTB4.ANWBLAT', 'LG', 531.59, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 1way (+Wifi / non Plasma) | ARNU24GTTB4.ANWBLAT', 'LG', 585.65, 'und'], ['HVAC', 'Accesorios HVAC', 'HEADER BRANCH / 10 BRANCH | ARBL1010.ENCXCOM', 'LG', 153.17, 'und'], ['HVAC', 'Accesorios HVAC', 'HEADER BRANCH / 4 BRANCH | ARBL104.ENCXCOM', 'LG', 99.11, 'und'], ['HVAC', 'Accesorios HVAC', 'HEADER BRANCH / 7 BRANCH | ARBL107.ENCXCOM', 'LG', 126.14, 'und'], ['HVAC', 'Accesorios HVAC', 'HEADER BRANCH / 10 BRANCH | ARBL2010.ENCXCOM', 'LG', 162.18, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 2way (+Wifi) | ARNU09GTSC4.ENWBLEU', 'LG', 522.58, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 2way (+Wifi) | ARNU12GTSC4.ENWBLEU', 'LG', 549.61, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 2way (+Wifi) | ARNU18GTSC4.ANWBLAT', 'LG', 585.65, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 2way (+Wifi) | ARNU24GTSC4.ANWBLAT', 'LG', 585.65, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A  \nMulti V sync\nY Branch | ARBLB01621.ENCXCOM', 'LG', 63.07, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / non plasma) | ARNU05GTRB4.ANWBLAT', 'LG', 459.51, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / non plasma) | ARNU07GTRB4.ANWBLAT', 'LG', 477.53, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / non plasma) | ARNU09GTRB4.ANWBLAT', 'LG', 495.55, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / non plasma) | ARNU12GTRB4.ANWBLAT', 'LG', 513.57, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / non plasma) | ARNU15GTQB4.ANWBLAT', 'LG', 531.59, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / non plasma) | ARNU18GTQB4.ANWBLAT', 'LG', 549.61, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / non plasma) | ARNU21GTQB4.ANWBLAT', 'LG', 585.65, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A  \nMulti V sync\nY Branch | ARBLB03321.ENCXCOM', 'LG', 117.13, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / non plasma) | ARNU54GTMA4.ANWBLAT', 'LG', 873.97, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A  \nMulti V sync\nY Branch | ARBLB07121.ENCXCOM', 'LG', 162.18, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A  \nMulti V sync\nY Branch | ARBLB14521.ENCXCOM', 'LG', 252.28, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / Non / Dual Vane) | ARNU24GTBB4.ANWBLAT', 'LG', 675.75, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / Non / Dual Vane) | ARNU28GTBB4.ANWBLAT', 'LG', 711.79, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / Non / Dual Vane) | ARNU30GTBB4.ANWBLAT', 'LG', 747.83, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / Non / Dual Vane) | ARNU36GTAB4.ANWBLAT', 'LG', 774.86, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / Non / Dual Vane) | ARNU42GTAB4.ANWBLAT', 'LG', 828.92, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi / Non / Dual Vane) | ARNU48GTAB4.ANWBLAT', 'LG', 891.99, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A  \nMulti V sync\nY Branch | ARBLB23220.ENCXCOM', 'LG', 468.52, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A  \nMulti V Plus\nY Branch | ARBLN01621.ENCXCOM', 'LG', 45.05, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A  \nMulti V Plus\nY Branch | ARBLN03321.ENCXCOM', 'LG', 54.06, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A  \nMulti V Plus\nY Branch | ARBLN07121.ENCXCOM', 'LG', 99.11, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A  \nMulti V Plus\nY Branch | ARBLN14521.ENCXCOM', 'LG', 171.19, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A  \nMulti V Plus\nY Branch | ARBLN23220.ENCXCOM', 'LG', 288.32, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Round CST | ARNU24GTYA4.ENWBLEU', 'LG', 882.98, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Round CST | ARNU36GTYA4.ENWBLEU', 'LG', 937.04, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Round CST | ARNU48GTYA4.ENWBLEU', 'LG', 1009.12, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A \nMulti V Sync (O/D Branch) | ARCNB21.ENCXCOM', 'LG', 162.18, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'CVT (+Wifi) | ARNU09GVEA4.ENWBLEU', 'LG', 513.57, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'CVT (+Wifi) | ARNU12GVEA4.ENWBLEU', 'LG', 531.59, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'CVT (+Wifi) | ARNU18GV1A4.ANWTLAT', 'LG', 639.71, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'CVT (+Wifi) | ARNU24GV1A4.ANWTLAT', 'LG', 666.74, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'CVT (+Wifi) | ARNU36GV2A4.ANWTLAT', 'LG', 846.94, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'CVT (+Wifi) | ARNU48GV2A4.ANWTLAT', 'LG', 1117.24, 'und'], ['HVAC', 'Ventilación y Extracción', 'Fresh Air Intake (+Wifi) | ARNU76GB8Z4.ANCSLAT', 'LG', 1603.78, 'und'], ['HVAC', 'Ventilación y Extracción', 'Fresh Air Intake (+Wifi) | ARNU96GB8Z4.ANCSLAT', 'LG', 1756.95, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU07GM1A4.ANCBLAT', 'LG', 558.62, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU09GM1A4.ANCBLAT', 'LG', 567.63, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU12GM1A4.ANCBLAT', 'LG', 585.65, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU15GM1A4.ANCBLAT', 'LG', 585.65, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU18GM1A4.ANCBLAT', 'LG', 594.66, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU24GM1A4.ANCBLAT', 'LG', 666.74, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU28GM2A4.ANCBLAT', 'LG', 693.77, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU36GM2A4.ANCBLAT', 'LG', 873.97, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU42GM2A4.ANCBLAT', 'LG', 882.98, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU48GM3B4.ANCBLAT', 'LG', 901.0, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU54GM3B4.ANCBLAT', 'LG', 1081.2, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU76GB8A4.ANCSLAT', 'LG', 1865.07, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU96GB8A4.ANCSLAT', 'LG', 2009.23, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU07GM1A4.ANCTLAT', 'LG', 558.62, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU09GM1A4.ANCTLAT', 'LG', 567.63, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU12GM1A4.ANCTLAT', 'LG', 585.65, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU15GM1A4.ANCTLAT', 'LG', 585.65, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU18GM1A4.ANCTLAT', 'LG', 594.66, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU24GM1A4.ANCTLAT', 'LG', 666.74, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU28GM2A4.ANCTLAT', 'LG', 693.77, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU36GM2A4.ANCTLAT', 'LG', 873.97, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU42GM2A4.ANCTLAT', 'LG', 882.98, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU48GM3B4.ANCTLAT', 'LG', 901.0, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (+Wifi) | ARNU54GM3B4.ANCTLAT', 'LG', 1081.2, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'UV Nano Filter box (M1 Chassis) | PBM13M1UA0.ENCXGLO', 'LG', 504.56, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'UV Nano Filter box (M2 Chassis) | PBM13M2UA0.ENCXGLO', 'LG', 540.6, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'UV Nano Filter box (M3 Chassis) | PBM13M3UA0.ENCXGLO', 'LG', 558.62, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Filter only  (M1 Chassis) | FBM13M1UA0.ENCXGLO', 'LG', 81.09, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Filter only  (M2 Chassis) | FBM13M2UA0.ENCXGLO', 'LG', 117.13, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Filter only  (M3 Chassis) | FBM13M3UA0.ENCXGLO', 'LG', 135.15, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (+Wifi) | ARNU05GL4G4.ANCTLAT', 'LG', 459.51, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (+Wifi) | ARNU07GL4G4.ANCTLAT', 'LG', 495.55, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (+Wifi) | ARNU09GL4G4.ANCTLAT', 'LG', 522.58, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (+Wifi) | ARNU12GL5G4.ANCTLAT', 'LG', 549.61, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (+Wifi) | ARNU15GL5G4.ANCTLAT', 'LG', 585.65, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (+Wifi) | ARNU18GL5G4.ANCTLAT', 'LG', 603.67, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (+Wifi) | ARNU21GL6G4.ANCTLAT', 'LG', 657.73, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (+Wifi) | ARNU24GL6G4.ANCTLAT', 'LG', 684.76, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation DX Coil (No Humidifier) | LZ-H050GXN4.ENWALEU', 'LG', 1892.1, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation DX Coil (No Humidifier) | LZ-H080GXN4.ENWALEU', 'LG', 1982.2, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation DX Coil (No Humidifier) | LZ-H100GXN4.ENWALEU', 'LG', 2045.27, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation DX Coil | LZ-H050GXH4.ENWALEU', 'LG', 2703.0, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation DX Coil | LZ-H080GXH4.ENWALEU', 'LG', 2793.1, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation DX Coil | LZ-H100GXH4.ENWALEU', 'LG', 2874.19, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation | LZ-H025GBA4.ENWSLEU', 'LG', 982.09, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation (ERV) | LZ-H035GBA5.ENWSLEU', 'LG', 1036.15, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation (ERV) | LZ-H050GBA5.ENWSLEU', 'LG', 1198.33, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation (ERV) | LZ-H080GBA5.ENWSLEU', 'LG', 1468.63, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation (ERV) | LZ-H100GBA5.ENWSLEU', 'LG', 1621.8, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation (ERV) | LZ-H150GBA5.ENWALEU', 'LG', 4054.5, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation (ERV) | LZ-H200GBA5.ENWALEU', 'LG', 4144.6, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand with case | ARNU07GCEA4.ENWBLEU', 'LG', 882.98, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand with case | ARNU09GCEA4.ENWBLEU', 'LG', 928.03, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand with case | ARNU12GCEA4.ENWBLEU', 'LG', 855.95, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand with case | ARNU15GCEA4.ENWBLEU', 'LG', 955.06, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand with case | ARNU18GCFA4.ENWBLEU', 'LG', 1018.13, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand with case | ARNU24GCFA4.ENWBLEU', 'LG', 1036.15, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand without case | ARNU07GCEU4.ENCBLEU', 'LG', 846.94, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand without case | ARNU09GCEU4.ENCBLEU', 'LG', 882.98, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand without case | ARNU12GCEU4.ENCBLEU', 'LG', 928.03, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand without case | ARNU15GCEU4.ENCBLEU', 'LG', 937.04, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand without case | ARNU18GCFU4.ENCBLEU', 'LG', 1018.13, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Floor Stand without case | ARNU24GCFU4.ENCBLEU', 'LG', 1036.15, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Console | ARNU07GQAA4.ENWBLEU', 'LG', 513.57, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Console | ARNU09GQAA4.ENWBLEU', 'LG', 522.58, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Console | ARNU12GQAA4.ENWBLEU', 'LG', 540.6, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Console | ARNU15GQAA4.ENWBLEU', 'LG', 567.63, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'CST | ATNQ22GPLA4.ANWTLPS', 'LG', 477.53, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'O/D | ATUQ22GPLA4.AWGTLPS', 'LG', 855.95, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Duct | ABNQ22GM1A4.ANWTLAT', 'LG', 432.48, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'O/D | ABUQ22GM1A4.AWGTLAT', 'LG', 855.95, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'CST | ATNQ30GPLA4.ANWTLPS', 'LG', 522.58, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'O/D | ATUQ30GPLA4.AWGTLPS', 'LG', 991.1, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Duct | ABNQ30GM1A4.ANWTLAT', 'LG', 504.56, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'O/D | ABUQ30GM1A4.AWGTLAT', 'LG', 991.1, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'CST | ATNQ40GNLA5.ENWTLPS', 'LG', 630.7, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Duct | ABNQ40GM3A5.ENWTLAT', 'LG', 675.75, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'CVT | AVNQ40GM1A5.ENWTLPS', 'LG', 675.75, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'O/D | AUUQ40GH5.EWGTLPS', 'LG', 1261.4, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'CST | ATNQ50GMLA5.ENWTLPS', 'LG', 666.74, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Duct | ABNQ50GM3A5.ENWTLAT', 'LG', 720.8, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'CVT | AVNQ50GM2A5.ENWTLPS', 'LG', 765.85, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'O/D | AUUQ50GH5.EWGTLPS', 'LG', 1531.7, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'CST | ATNQ60GMLA5.ENWTLPS', 'LG', 693.77, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Duct | ABNQ60GM3A5.ENWTLAT', 'LG', 765.85, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'CVT | AVNQ60GM2A5.ENWTLPS', 'LG', 801.89, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'O/D | AUUQ60GH5.EWGTLPS', 'LG', 1774.97, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Ducted Split | ANNQ60GKA4.ANWBLCB', 'LG', 1531.7, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Ducted Split O/D | AUUQ60GH4.AWGTLPS', 'LG', 1756.95, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'CVT Heat Pump 380V | AVNW60LM2S0.ANWTLAR', 'LG', 738.82, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'CVT Heat Pump 380V | AVUW60LM2S0.AWGTLAR', 'LG', 1774.97, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'Round type CST | ATNW40GYLS3.ENWBLPS', 'LG', 774.86, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'Round type CST | ATNW60GYLS3.ENWBLPS', 'LG', 1009.12, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'Round type CST O/D | AUUW40GH3.EWGTLPS', 'LG', 1306.45, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'Round type CST O/D | AUUW60GH3.EWGTLPS', 'LG', 1792.99, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'Round type CST | ATNW60GYLS3.ENWBLAT', 'LG', 774.86, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'Round type CST O/D | ATUW60GYLS3.EWGTLAT', 'LG', 1306.45, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'Round type CST | ATNW40GYLS3.ENWBLAT', 'LG', 1009.12, 'und'], ['HVAC', 'Aire Acondicionado Single Split', 'Round type CST O/D | ATUW40GYLS3.EWGTLAT', 'LG', 1792.99, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package Horizontal 1Phase | AK-Q036GH50.AWGBLAT', 'LG', 3622.02, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package Horizontal 1Phase | AK-Q048GH50.AWGBLAT', 'LG', 3730.14, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package Horizontal 1Phase | AK-Q060GH50.AWGBLAT', 'LG', 3811.23, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package 3 Phase | AK-W090BC00.ADGTLAT', 'LG', 9983.08, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package 3 Phase | AK-W120BC00.ADGTLAT', 'LG', 10487.64, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package 3 Phase | AK-W150BC00.ADGTLAT', 'LG', 13983.52, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package 3 Phase | AK-W180BC00.ADGTLAT', 'LG', 14479.07, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package 3 Phase | AK-W240BC00.ADGTLAT', 'LG', 18479.51, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package 3 Phase | AK-W300BC00.ADGTLAT', 'LG', 19975.17, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package 3 Phase | AK-W240DC00.ADGTLAT', 'LG', 18479.51, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package 3 Phase | AK-W300DC00.ADGTLAT', 'LG', 19975.17, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package (380V, 50Hz) | AK-W240LC00.AWGTLCL', 'LG', 18479.51, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'Single Package (380V, 50Hz) | AK-W300LC00.AWGTLCL', 'LG', 19975.17, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A \nMulti V Sync (O/D Branch) | ARCNB31.ENCXCOM', 'LG', 252.28, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'O/D (H/P) | A4UW24GFA4.EWGTLAR', 'LG', 1036.15, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'O/D (H/P) | A5UW30GFA4.EWGTLAR', 'LG', 1315.46, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'O/D (H/P) | A5UW48GFA4.EWGTLAR', 'LG', 1937.15, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'O/D F Dx (H/P) | FM40AH.U34', 'LG', 2054.28, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'O/D F Dx (H/P) | FM48AH.U34', 'LG', 2108.34, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'O/D F Dx (H/P) | FM56AH.U34', 'LG', 2162.4, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'SRAC (H/P) | AMNW09GSJA0.AMBTLAT', 'LG', 243.27, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'SRAC (H/P) | AMNW12GSJA0.AMBTLAT', 'LG', 252.28, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'SRAC (H/P) | AMNW18GSKA0.AMBTLAT', 'LG', 333.37, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'SRAC (H/P) | AMNW24GSKA0.AMBTLAT', 'LG', 342.38, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'Artcool (H/P) | AMNW09GSJR0.AMBTLAT', 'LG', 414.46, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'Artcool (H/P) | AMNW12GSJR0.AMBTLAT', 'LG', 423.47, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'Artcool (H/P) | AMNW18GSKR0.AMBTLAT', 'LG', 513.57, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'Artcool (H/P) | AMNW24GSKR0.AMBBEMS', 'LG', 576.64, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'CST 1way (H/P) | AMNW09GTUC0.ANWALAT', 'LG', 396.44, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'CST 1way (H/P) | AMNW12GTUC0.ANWALAT', 'LG', 414.46, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'CST 1way (H/P) | AMNW18GTTC0.ANWABRZ', 'LG', 423.47, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'CST 4way (H/P) | AMNW09GTRA1.ANWALAT', 'LG', 360.4, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'CST 4way (H/P) | AMNW12GTRA1.ANWALAT', 'LG', 369.41, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'CST 4way (H/P) | AMNW18GTQA1.ANWALAT', 'LG', 387.43, 'und'], ['HVAC', 'Aire Acondicionado Multi Split', 'CST 4way (H/P) | AMNW24GTPA1.ANWALAT', 'LG', 468.52, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (H/P) | AMNW09GL1A2.ANWALAT', 'LG', 423.47, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (H/P) | AMNW12GL2A2.ANWALAT', 'LG', 486.54, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (H/P) | AMNW18GL2A2.ANWALAT', 'LG', 522.58, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct (H/P) | AMNW24GL3A2.ANWALAT', 'LG', 558.62, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'M Duct (H/P) | AMNW18GM1A0.ANWALAT', 'LG', 522.58, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'M Duct (H/P) | AMNW24GM1A0.ANWALAT', 'LG', 558.62, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A \nMulti V Sync (O/D Branch) | ARCNB41.ENCXCOM', 'LG', 342.38, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A \nMulti V Plus (O/D Branch) | ARCNN21.ENCXCOM', 'LG', 117.13, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A \nMulti V Plus (O/D Branch) | ARCNN31.ENCXCOM', 'LG', 117.13, 'und'], ['HVAC', 'Accesorios HVAC', 'R-410A \nMulti V Plus (O/D Branch) | ARCNN41.ENCXCOM', 'LG', 189.21, 'und'], ['HVAC', 'Accesorios HVAC', 'Multi V Hydro Kit (Low Temp) | ARNH04GK2A4.ENWALEU', 'LG', 2495.77, 'und'], ['HVAC', 'Accesorios HVAC', 'Multi V Hydro Kit (High Temp) | ARNH04GK3A4.ENWALEU', 'LG', 5460.06, 'und'], ['HVAC', 'Accesorios HVAC', 'Multi V Hydro Kit (High Temp) | ARNH08GK3A4.ENWALEU', 'LG', 6532.25, 'und'], ['HVAC', 'Accesorios HVAC', 'FIXED MULTI O/D (C/O) | A2UQ18GFAB.EWGTLAT', 'LG', 612.68, 'und'], ['HVAC', 'Accesorios HVAC', 'FIXED MULTI O/D (C/O) | A3UQ24GFAB.EWGTLAT', 'LG', 702.78, 'und'], ['HVAC', 'Accesorios HVAC', 'FIXED MULTI O/D (C/O) | A3UQ34GFAB.EWGTLAT', 'LG', 891.99, 'und'], ['HVAC', 'Accesorios HVAC', 'FIXED MULTI I/D (SRAC) | AMNQ09GSJAA.ENWTLAT', 'LG', 216.24, 'und'], ['HVAC', 'Accesorios HVAC', 'FIXED MULTI I/D (SRAC) | AMNQ12GSJAA.ENWTLAT', 'LG', 234.26, 'und'], ['HVAC', 'Accesorios HVAC', 'FIXED MULTI I/D (SRAC) | AMNQ18GSKAA.ENWTLAT', 'LG', 288.32, 'und'], ['HVAC', 'Accesorios HVAC', 'FIXED MULTI I/D (SRAC) | AMNQ24GSKAA.ENWTLAT', 'LG', 324.36, 'und'], ['HVAC', 'Accesorios HVAC', 'Multi V Hydro Kit (Low Temp) | ARNH10GK2A4.ENWALEU', 'LG', 2856.17, 'und'], ['HVAC', 'Accesorios HVAC', 'AC-EZ Touch | PACEZA000.ENCXLEU', 'LG', 504.56, 'und'], ['HVAC', 'Automatización y Control HVAC', 'AC Manager 5 (SW) | PACM5A000.ENCXLEU', 'LG', 3099.44, 'und'], ['HVAC', 'Automatización y Control HVAC', 'ACP 5 (Bacnet embeded) | PACP5A000.ENCXLEU', 'LG', 2252.5, 'und'], ['HVAC', 'Automatización y Control HVAC', 'AC Smart 5 (Bacnet embeded) | PACS5A000.ENCXLEU', 'LG', 1802.0, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Comm Kit (module) DC12V | PAHCMC000.ENCXLEU', 'LG', 423.47, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Comm Kit (Controller) DC12V | PAHCMM000.ENCXCOM', 'LG', 540.6, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Comm Kit (Return) AC 220V | PAHCMR000.ENCSLEU', 'LG', 720.8, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Comm Kit (Supply) AC 220V | PAHCMS000.ENCSLEU', 'LG', 901.0, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Comm Control kit AC 220V | PAHCNM000.ENCSCOM', 'LG', 2234.48, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Expansion Kits | PATX13A0E.ENCXCOM', 'LG', 531.59, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Expansion Kits | PATX20A0E.ENCXCOM', 'LG', 612.68, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Expansion Kits | PATX25A0E.ENCXCOM', 'LG', 648.72, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Expansion Kits | PATX35A0E.ENCXCOM', 'LG', 819.91, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Expansion Kits | PATX50A0E.ENCXCOM', 'LG', 1000.11, 'und'], ['HVAC', 'Automatización y Control HVAC', 'I/O Module (Chiller Kit) | PCHLLN000.ENCXLEU', 'LG', 207.23, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Dry Contact AC 220V (1 port) | PDRYCB000.ENCXCOM', 'LG', 72.08, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Dry Contact 24V | PDRYCB100.ENCXLEU', 'LG', 72.08, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Dry Contact (8 Port) | PDRYCB300.ENCXLEU', 'LG', 81.09, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Dry Contact (8 Port + Universal I/O) | PDRYCB320.ENCXLEU', 'LG', 99.11, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Dry Contact (2 Port) | PDRYCB400.ENCXLEU', 'LG', 99.11, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Dry Contact Modbus | PDRYCB500.ENCXCOM', 'LG', 81.09, 'und'], ['HVAC', 'Automatización y Control HVAC', 'ACS Expansion I/O Module | PEXPMB000.ENCXLEU', 'LG', 558.62, 'und'], ['HVAC', 'Automatización y Control HVAC', 'I/O Module (UI) | PEXPMB100.ENCXCOM', 'LG', 207.23, 'und'], ['HVAC', 'Automatización y Control HVAC', 'I/O Module (UO) | PEXPMB200.ENCXCOM', 'LG', 207.23, 'und'], ['HVAC', 'Automatización y Control HVAC', 'I/O Module (UIO) | PEXPMB300.ENCXCOM', 'LG', 207.23, 'und'], ['HVAC', 'Automatización y Control HVAC', 'PI485 (IDU) | PHNFP14A0.ENCXCOM', 'LG', 45.05, 'und'], ['HVAC', 'Accesorios HVAC', 'Economizer (new heat pump lineup) | PKEMD1CA0.ENCXLAT', 'LG', 2207.45, 'und'], ['HVAC', 'Automatización y Control HVAC', 'LGMV Wifi module | PLGMVW100.ENCXLEU', 'LG', 360.4, 'und'], ['HVAC', 'Automatización y Control HVAC', 'LON Gateway DC12V | PLNWKB000.ENCXLEU', 'LG', 1243.38, 'und'], ['HVAC', 'Automatización y Control HVAC', 'LON Gateway AC24V | PLNWKB100.ENCXLUS', 'LG', 2036.26, 'und'], ['HVAC', 'Accesorios HVAC', 'Multi ACC | PMBD3620.ENCXLEU', 'LG', 261.29, 'und'], ['HVAC', 'Accesorios HVAC', 'Multi ACC | PMBD3630.ENCXLEU', 'LG', 306.34, 'und'], ['HVAC', 'Accesorios HVAC', 'Multi ACC | PMBD3640.ENCXLEU', 'LG', 342.38, 'und'], ['HVAC', 'Accesorios HVAC', 'Multi ACC | PMBL1203F0.ENCXLEU', 'LG', 153.17, 'und'], ['HVAC', 'Accesorios HVAC', 'Multi ACC | PMBL3620.ENCXLEU', 'LG', 81.09, 'und'], ['HVAC', 'Accesorios HVAC', 'Multi ACC | PMBL4820.ENCXLEU', 'LG', 72.08, 'und'], ['HVAC', 'Accesorios HVAC', 'Multi ACC | PMBL5620.ENCXLEU', 'LG', 81.09, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Modbus RTU (ODU) | PMBUSB00A.ENCXLEU', 'LG', 252.28, 'und'], ['HVAC', 'Automatización y Control HVAC', 'PI485 (ODU) | PMNFP14A1.ENCXCOM', 'LG', 76.59, 'und'], ['HVAC', 'Accesorios HVAC', 'New PDI (2 port) | PPWRDB000.ENCXLEU', 'LG', 432.48, 'und'], ['HVAC', 'Accesorios HVAC', 'Air Guide | PQAGA.ENCXLEU', 'LG', 108.12, 'und'], ['HVAC', 'Accesorios HVAC', '128 room Exp. Kit | PQCSE440U0.ENCXLEU', 'LG', 162.18, 'und'], ['HVAC', 'Accesorios HVAC', 'AC-EZ | PQCSZ250S0.ENCXCOM', 'LG', 189.21, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Dry Contact | PQDSA.ENCXLEU', 'LG', 36.04, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Dry Contact (ODU) | PQDSBCDVM0.ENCXCOM', 'LG', 99.11, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Digital Output Kit | PQNFP00T0.ENCXLEU', 'LG', 189.21, 'und'], ['HVAC', 'Accesorios HVAC', 'New PDI (8 port) | PQNUD1S40.ENCXCOM', 'LG', 1405.56, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Simple Wired Remote (B/Big/Hotel) | PQRCHCA0Q.ENCXCOM', 'LG', 63.07, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Simple Wired Remote (W/Big/Hotel) | PQRCHCA0QW.ENCXCOM', 'LG', 63.07, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Simple Wired Remote (B/Small) | PQRCVCL0Q.ENCXLEU', 'LG', 72.08, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Simple Wired Remote (W/Small) | PQRCVCL0QW.ENCXCOM', 'LG', 72.08, 'und'], ['HVAC', 'Accesorios HVAC', 'Temperature remote sensor | PQRSTA0.ENCXCOM', 'LG', 27.03, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Control Kits | PRCKD21E.ENCXLEU', 'LG', 3108.45, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Control Kits | PRCKD41E.ENCXLEU', 'LG', 3378.75, 'und'], ['HVAC', 'Automatización y Control HVAC', 'LGMV | PRCTIL0.ENCXLEU', 'LG', 540.6, 'und'], ['HVAC', 'Accesorios HVAC', 'Cool/Heat Selector | PRDSBM.ENCXCOM', 'LG', 54.06, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Premium Wired Remote | PREMTA000.ENCXCOM', 'LG', 306.34, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Standard Wired Remote (W) RS2 | PREMTB001.ENCXCOM', 'LG', 117.13, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Standard Wired Remote (W) RS3 | PREMTB101.ENCXCOM', 'LG', 162.18, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Premium Wired Remote (US) | PREMTB10U.ENCXLUS', 'LG', 108.12, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Standard Wired Remote (B) RS2 | PREMTBB01.ENCXLEU', 'LG', 117.13, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Standard Wired Remote (B) RS3 | PREMTBB10.ENCXLEU', 'LG', 162.18, 'und'], ['HVAC', 'Accesorios HVAC', 'EEV External Valve | PRGK024A0.ENCXLEU', 'LG', 207.23, 'und'], ['HVAC', 'Accesorios HVAC', 'R410A \nH/R unit | PRHR023.ENCXLEU', 'LG', 1072.19, 'und'], ['HVAC', 'Accesorios HVAC', 'R410A \nH/R unit | PRHR033.ENCXLEU', 'LG', 1333.48, 'und'], ['HVAC', 'Accesorios HVAC', 'R410A \nH/R unit | PRHR043.ENCXLEU', 'LG', 1603.78, 'und'], ['HVAC', 'Accesorios HVAC', 'R410A \nH/R unit | PRHR063.ENCXLEU', 'LG', 2108.34, 'und'], ['HVAC', 'Accesorios HVAC', 'R410A \nH/R unit | PRHR083.ENCXLEU', 'LG', 3396.77, 'und'], ['HVAC', 'Accesorios HVAC', 'Refrigerant Leakage Detector | PRLDNVS0.ENCXLEU', 'LG', 81.09, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU EEV Kit | PRLK048A0.ENCXCOM', 'LG', 234.26, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU EEV Kit | PRLK096A0.ENCXCOM', 'LG', 261.29, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU EEV Kit | PRLK396A0.ENCXCOM', 'LG', 585.65, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU EEV Kit | PRLK594A0..ENCXCOM', 'LG', 855.95, 'und'], ['HVAC', 'Accesorios HVAC', 'Stopper Valve | PRVT120.ENCXCOM', 'LG', 45.05, 'und'], ['HVAC', 'Accesorios HVAC', 'Stopper Valve | PRVT780.ENCXCOM', 'LG', 99.11, 'und'], ['HVAC', 'Accesorios HVAC', 'Stopper Valve | PRVT980.ENCXCOM', 'LG', 108.12, 'und'], ['HVAC', 'Accesorios HVAC', '4way Dual Vane Panel non Air Puri | PT-AAGW0.ENCXCOM', 'LG', 166.69, 'und'], ['HVAC', 'Accesorios HVAC', '4way Dual Vane Panel Air Puri | PT-AFGW0.ENCXCOM', 'LG', 252.28, 'und'], ['HVAC', 'Accesorios HVAC', '4way Dual Vane Panel Air Puri & auto elevation | PT-AFGW0.ENCXCOM', 'LG', 252.28, 'und'], ['HVAC', 'Accesorios HVAC', '4way Air Puri Kit | PTAHMP0.ENCXCOM', 'LG', 441.49, 'und'], ['HVAC', 'Accesorios HVAC', '1way Air Puri Kit | PTAHTP0.ENCXCOM', 'LG', 225.25, 'und'], ['HVAC', 'Accesorios HVAC', '1way Air Puri Kit | PTAHTP0.ENCXCOM', 'LG', 225.25, 'und'], ['HVAC', 'Accesorios HVAC', 'Round CST Air Puri Kit | PTAHYP0.ENCXGLO', 'LG', 441.49, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Decoration Cover | PTDCD.ENCXLEU', 'LG', 108.12, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Decoration Cover | PTDCD1.ENCXLEU', 'LG', 108.12, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Decoration Cover | PTDCM.ENCXLEU', 'LG', 99.11, 'und'], ['HVAC', 'Accesorios HVAC', 'AHU Decoration Cover | PTDCQ.ENCXLEU', 'LG', 76.59, 'und'], ['HVAC', 'Accesorios HVAC', '4way auto elevation grill kit | PTEGM0.ENCXLEU', 'LG', 288.32, 'und'], ['HVAC', 'Accesorios HVAC', 'CST 2way | PT-HLC1.ANCXLUS', 'LG', 153.17, 'und'], ['HVAC', 'Accesorios HVAC', '4way Panel Air Puri for TM,TN,TP | PT-MPGW0.ENCXCOM', 'LG', 189.21, 'und'], ['HVAC', 'Accesorios HVAC', '4way Plasma filter kit | PTPKM0.ENCXLEU', 'LG', 45.05, 'und'], ['HVAC', 'Accesorios HVAC', '4way Panel (5 ~ 21K) grid | PT-QAGW0.ENCXCOM', 'LG', 117.13, 'und'], ['HVAC', 'Accesorios HVAC', '1way Panel (18~24K) non Air Puri | PT-TAHG0.ENCXGLO', 'LG', 171.19, 'und'], ['HVAC', 'Accesorios HVAC', '1way Panel (18~24K) non Air Puri | PT-TAHW0.ENCXCOM', 'LG', 171.19, 'und'], ['HVAC', 'Accesorios HVAC', '1way Panel (18~24K) Air Puri | PT-TPHG0.ENCXCOM', 'LG', 180.2, 'und'], ['HVAC', 'Accesorios HVAC', '1way Panel (7~12K) non Air Puri (Gray) | PT-UAHG0.ENCXGLO', 'LG', 135.15, 'und'], ['HVAC', 'Accesorios HVAC', '1way Panel (7~12K) non Air Puri (White) | PT-UAHW0.ENCXCOM', 'LG', 135.15, 'und'], ['HVAC', 'Accesorios HVAC', 'CST 4way Panel | PT-UMC1.ENCXLUS', 'LG', 126.14, 'und'], ['HVAC', 'Accesorios HVAC', '1way Panel (7~12K) Air Puri | PT-UPHG0.ENCXCOM', 'LG', 162.18, 'und'], ['HVAC', 'Accesorios HVAC', '2way Panel grid | PT-USC.ENCXCOM', 'LG', 153.17, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation Kit for CST\n(Fresh Kit) | PTVK410.ENCXLUS', 'LG', 135.15, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation Kit for CST\n(Fresh Kit) | PTVK420.ENCXLUS', 'LG', 45.05, 'und'], ['HVAC', 'Ventilación y Extracción', 'Ventilation Kit for CST\n(Fresh Kit) | PTVK430.ENCXLUS', 'LG', 9.01, 'und'], ['HVAC', 'Accesorios HVAC', 'Human Sensing kit | PTVSAA0.ENCXCOM', 'LG', 117.13, 'und'], ['HVAC', 'Accesorios HVAC', 'nan | PTVSMA0.ENCXLEU', 'LG', 126.14, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Dry Contact (ODU/MultiV 4,5,S,W) | PVDSMN000.ENCXLEU', 'LG', 207.23, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Wi-fi Controller | PWFMDD200.ENCXLEU', 'LG', 54.06, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Wireless Remote (C/O) | PWLSSB21C.ENCXLEU', 'LG', 36.04, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V Mini (220V) | ARUN060GSS4.EWGBLUS', 'LG', 3396.77, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S  Heat Recovery | ARUM036GSS5.EWGBLUS', 'LG', 3423.8, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S  Heat Recovery | ARUM048GSS5.EWGBLUS', 'LG', 3604.0, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'O/D Multi V S  Heat Recovery | ARUB060GSS4.EWGBLUS', 'LG', 3874.3, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (220V) | ARWM072BAS5.AWGBLUS', 'LG', 6757.5, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (220V) | ARWM096BAS5.AWGBLUS', 'LG', 7298.1, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (220V) | ARWM121BAS5.AWGBLUS', 'LG', 7838.7, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (220V) | ARWM144BAS5.AWGBLUS', 'LG', 8379.3, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) | ARWM072DAS5.AWGBLUS', 'LG', 6757.5, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) | ARWM096DAS5.AWGBLUS', 'LG', 7298.1, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) | ARWM121DAS5.AWGBLUS', 'LG', 7838.7, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) | ARWM144DAS5.AWGBLUS', 'LG', 8379.3, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) | ARWM168DAS5.AWGBLUS', 'LG', 8919.9, 'und'], ['HVAC', 'Sistemas de Agua Helada (Chiller)', 'O/D Multi V Water H/R (460V) | ARWM192DAS5.AWGBLUS', 'LG', 9460.5, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC | ARNU053SJA4.AMBBLUS', 'LG', 387.43, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC | ARNU073SJA4.AMBBLUS', 'LG', 396.44, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC | ARNU093SJA4.AMBBLUS', 'LG', 405.45, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC | ARNU123SJA4.AMBBLUS', 'LG', 423.47, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC | ARNU153SJA4.AMBBLUS', 'LG', 441.49, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC | ARNU183SKA4.AMBBLUS', 'LG', 513.57, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC | ARNU243SKA4.AMBBLUS', 'LG', 540.6, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC | ARNU303SVA4.AMBALUS', 'LG', 855.95, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'SRAC | ARNU363SVA4.AMBALUS', 'LG', 901.0, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool | ARNU053SJR4.ANCBLUS', 'LG', 468.52, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool | ARNU073SJR4.ANCBLUS', 'LG', 477.53, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool | ARNU093SJR4.ANCBLUS', 'LG', 486.54, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool | ARNU123SJR4.ANCBLUS', 'LG', 513.57, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool | ARNU153SJR4.ANCBLUS', 'LG', 531.59, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool | ARNU183SKR4.ANCBLUS', 'LG', 612.68, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Artcool | ARNU243SKR4.ANCBLUS', 'LG', 657.73, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 1way (+Wifi) | ARNU073TUD4.ANWBLUS', 'LG', 432.48, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 1way (+Wifi) | ARNU093TUD4.ANWBLUS', 'LG', 468.52, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 1way (+Wifi) | ARNU123TUD4.ANWBLUS', 'LG', 504.56, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 1way (+Wifi) | ARNU183TTD4.ANWBLUS', 'LG', 531.59, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 1way (+Wifi) | ARNU243TTD4.ANWBLUS', 'LG', 585.65, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 1way Panel (TT chassis) | PT-TAHW0.ENCXLUS', 'LG', 135.15, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 2way | ARNU183TSA4.ANWBLUS', 'LG', 576.64, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 2way | ARNU243TSA4.ANWBLUS', 'LG', 603.67, 'und'], ['HVAC', 'Automatización y Control HVAC', 'Wireless Remote (H/P) | PWLSSB21H.EXCXLEU', 'LG', 36.04, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi) 2X2 | ARNU053TRD4.ANWALUS', 'LG', 459.51, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi) 2X2 | ARNU073TRD4.ANWALUS', 'LG', 477.53, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi) 2X2 | ARNU093TRD4.ANWALUS', 'LG', 495.55, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi) 2X2 | ARNU123TRD4.ANWALUS', 'LG', 513.57, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi) 2X2 | ARNU153TQD4.ANWALUS', 'LG', 531.59, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (+Wifi) 2X2 | ARNU183TQD4.ANWALUS', 'LG', 549.61, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST mini 4way Panel (620X620) | PT-QAGW0.ENCXLUS', 'LG', 135.15, 'und'], ['HVAC', 'Accesorios HVAC', 'Group control Wire | PZCWRCG3.ENCXCOM', 'LG', 27.03, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (Dual Vane) | ARNU073TAA4.ANWALUS', 'LG', 855.95, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (Dual Vane) | ARNU093TAA4.ANWALUS', 'LG', 891.99, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (Dual Vane) | ARNU123TAA4.ANWALUS', 'LG', 946.05, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (Dual Vane) | ARNU153TAA4.ANWALUS', 'LG', 991.1, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (Dual Vane) | ARNU183TAA4.ANWALUS', 'LG', 1054.17, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (Dual Vane) | ARNU243TAA4.ANWALUS', 'LG', 1108.23, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (Dual Vane) | ARNU283TAA4.ANWALUS', 'LG', 1171.3, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (Dual Vane) | ARNU363TAA4.ANWALUS', 'LG', 1216.35, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (Dual Vane) | ARNU423TAA4.ANWALUS', 'LG', 1261.4, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'CST 4way (Dual Vane) | ARNU483TAA4.ANWALUS', 'LG', 1324.47, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Small Chassis) | ARNU073M1A4.ANWALUS', 'LG', 657.73, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Small Chassis) | ARNU093M1A4.ANWALUS', 'LG', 684.76, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Small Chassis) | ARNU123M1A4.ANWALUS', 'LG', 729.81, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Small Chassis) | ARNU153M1A4.ANWALUS', 'LG', 783.87, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Small Chassis) | ARNU183M1A4.ANWALUS', 'LG', 837.93, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Small Chassis) | ARNU243M1A4.ANWALUS', 'LG', 882.98, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Large Chassis) | ARNU283M2A4.ANWALUS', 'LG', 964.07, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Large Chassis) | ARNU363M2A4.ANWALUS', 'LG', 1207.34, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Large Chassis) | ARNU423M2A4.ANWALUS', 'LG', 1279.42, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Large Chassis) | ARNU483M3A4.ANWALUS', 'LG', 1369.52, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Large Chassis) | ARNU543M3A4.ANWALUS', 'LG', 1405.56, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Large Chassis) | ARNU763B8A4.ANWSLUS', 'LG', 2333.59, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (Large Chassis) | ARNU963B8A4.ANWSLUS', 'LG', 2351.61, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (High Efficiency) | ARNU073M2A4.ANWALUS', 'LG', 747.83, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (High Efficiency) | ARNU093M2A4.ANWALUS', 'LG', 774.86, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (High Efficiency) | ARNU123M2A4.ANWALUS', 'LG', 819.91, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (High Efficiency) | ARNU153M2A4.ANWALUS', 'LG', 846.94, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (High Efficiency) | ARNU183M2A4.ANWALUS', 'LG', 873.97, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (High Efficiency) | ARNU243M2A4.ANWALUS', 'LG', 919.02, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'H Duct (High Efficiency) | ARNU283M3A4.ANWALUS', 'LG', 1036.15, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct | ARNU073L1G4.ANWALUS', 'LG', 495.55, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct | ARNU093L1G4.ANWALUS', 'LG', 522.58, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct | ARNU123L2G4.ANWALUS', 'LG', 549.61, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct | ARNU153L2G4.ANWALUS', 'LG', 585.65, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct | ARNU183L2G4.ANWALUS', 'LG', 603.67, 'und'], ['HVAC', 'Ductos y Manejadoras de Aire', 'L Duct | ARNU243L3G4.ANWALUS', 'LG', 684.76, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Ceiling | ARNU183V1A4.ANWALUS', 'LG', 720.8, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Ceiling | ARNU243V1A4.ANWALUS', 'LG', 720.8, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Ceiling | ARNU363V2A4.ANWALUS', 'LG', 783.87, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Ceiling | ARNU483V2A4.ANWALUS', 'LG', 783.87, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Eco V | ARVU053ZEA2.ENWALUS', 'LG', 1765.96, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Eco V | ARVU063ZEA2.ENWALUS', 'LG', 2054.28, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Eco V | ARVU093ZFA2.ENWALUS', 'LG', 3676.08, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Eco V | ARVU123ZFA2.ENWALUS', 'LG', 3964.4, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Hydro Kit (Mid temp) | ARNH963K2A4.ANWALUS', 'LG', 5189.76, 'und'], ['HVAC', 'Ventilación y Extracción', 'Fresh Air Intake | ARNU763B8Z4.ANWSLUS', 'LG', 1342.49, 'und'], ['HVAC', 'Ventilación y Extracción', 'Fresh Air Intake | ARNU963B8Z4.ANWSLUS', 'LG', 1405.56, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Vertical Air Handler Unit | ARNU123NJA4.AMBBLUS', 'LG', 1468.63, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Vertical Air Handler Unit | ARNU183NJA4.AMBBLUS', 'LG', 1495.66, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Vertical Air Handler Unit | ARNU243NJA4.AMBBLUS', 'LG', 1558.73, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Vertical Air Handler Unit | ARNU303NJA4.AMBBLUS', 'LG', 1603.78, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Vertical Air Handler Unit | ARNU363NJA4.AMBBLUS', 'LG', 1630.81, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Vertical Air Handler Unit | ARNU423NKA4.AMBBLUS', 'LG', 1693.88, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Vertical Air Handler Unit | ARNU483NKA4.AMBBLUS', 'LG', 1783.98, 'und'], ['HVAC', 'Aire Acondicionado VRF / Multi V', 'Vertical Air Handler Unit | ARNU543NKA4.AMBBLUS', 'LG', 1838.04, 'und'], ['HVAC', 'Accesorios HVAC', 'CST 4way (regular only) | LCN098HV4.BWHBEUS', 'LG', 387.43, 'und'], ['HVAC', 'Accesorios HVAC', 'L Duct (regular only) | LDN097HV4.BWHBEUS', 'LG', 400.95, 'und'], ['HVAC', 'Accesorios HVAC', 'Console | LQN090HV4.ENWBEUS', 'LG', 414.46, 'und'], ['HVAC', 'Accesorios HVAC', 'Universal O/D (regular) | LUU090HV.EWGHEUS', 'LG', 819.91, 'und'], ['HVAC', 'Accesorios HVAC', 'CST 4way (regular only) | LCN128HV4.BWHBEUS', 'LG', 360.4, 'und'], ['HVAC', 'Accesorios HVAC', 'L Duct (regular only) | LDN127HV4.BWHBEUS', 'LG', 457.43, 'und'], ['HVAC', 'Accesorios HVAC', 'Console | LQN120HV4.ENWBEUS', 'LG', 457.43, 'und'], ['HVAC', 'Accesorios HVAC', 'Universal O/D (regular) | LUU120HV.EWGHEUS', 'LG', 901.0, 'und'], ['HVAC', 'Accesorios HVAC', 'CST 4way (regular & RED) | LCN188HV4.BWHBEUS', 'LG', 500.06, 'und'], ['HVAC', 'Accesorios HVAC', 'L Duct (regular & RED) | LDN187HV4.BWHBEUS', 'LG', 594.66, 'und'], ['HVAC', 'Accesorios HVAC', 'Vertical AHU (Ducted Split) | LVN181HV4.ENWBEUS', 'LG', 1504.67, 'und'], ['HVAC', 'Accesorios HVAC', 'Universal O/D (regular) | LUU180HV.EWGHEUS', 'LG', 1401.06, 'und'], ['HVAC', 'Accesorios HVAC', 'H Duct (regular & RED) | LHN248HV.ENWAEUS', 'LG', 747.83, 'und'], ['HVAC', 'Accesorios HVAC', 'Vertical AHU (Ducted Split) | LVN241HV4.ENWBEUS', 'LG', 1549.72, 'und'], ['HVAC', 'Accesorios HVAC', 'Universal O/D (regular) | LUU240HV.EWGHEUS', 'LG', 1401.06, 'und'], ['HVAC', 'Accesorios HVAC', 'H Duct (regular & RED) | LHN368HV.ENWAEUS', 'LG', 1072.19, 'und'], ['HVAC', 'Accesorios HVAC', 'Vertical AHU (Ducted Split) | LVN361HV4.ENWBEUS', 'LG', 1747.94, 'und'], ['HVAC', 'Accesorios HVAC', 'Universal O/D (regular) | LUU360HV.EWGHEUS', 'LG', 1995.72, 'und'], ['HVAC', 'Accesorios HVAC', 'Vertical AHU (Ducted Split) | LVN420HV.ENWBEUS', 'LG', 1820.02, 'und'], ['HVAC', 'Accesorios HVAC', 'Universal O/D (regular) | LUU420HV.EWGHEUS', 'LG', 1315.46, 'und'], ['HVAC', 'Accesorios HVAC', 'Vertical AHU (Ducted Split) | LVN480HV.ENWBEUS', 'LG', 1901.11, 'und'], ['HVAC', 'Accesorios HVAC', 'Universal O/D (regular) | LUU480HV.EWGHEUS', 'LG', 2495.77, 'und'], ['HVAC', 'Accesorios HVAC', 'RED CST 4way (High Heat) Dual vane | LCN249HV.ANWBEUS', 'LG', 554.12, 'und'], ['HVAC', 'Accesorios HVAC', 'RED CST 4way (High Heat) Dual vane | LCN369HV.ANWBEUS', 'LG', 693.77, 'und'], ['HVAC', 'Accesorios HVAC', 'RED CST 4way (High Heat) Dual vane | LCN429HV.ANWBEUS', 'LG', 833.42, 'und'], ['HVAC', 'Accesorios HVAC', 'RED CST 4way (High Heat) Dual vane | LCN489HV.ANWBEUS', 'LG', 973.08, 'und'], ['HVAC', 'Accesorios HVAC', 'RED H Duct (High Heat) | LHN428HV.ENWAEUS', 'LG', 901.0, 'und'], ['HVAC', 'Accesorios HVAC', 'RED H Duct (High Heat) | LHN488HV.ENWAEUS', 'LG', 1040.66, 'und'], ['HVAC', 'Accesorios HVAC', 'RED O/D (High Heat) | LUU180HHV.EWGBEUS', 'LG', 1941.66, 'und'], ['HVAC', 'Accesorios HVAC', 'RED O/D (High Heat) | LUU240HHV.EWGBEUS', 'LG', 2216.46, 'und'], ['HVAC', 'Accesorios HVAC', 'RED O/D (High Heat) | LUU360HHV.EWGBEUS', 'LG', 2495.77, 'und'], ['HVAC', 'Accesorios HVAC', 'RED O/D (High Heat) | LUU420HHV.EWGBEUS', 'LG', 2775.08, 'und'], ['HVAC', 'Accesorios HVAC', 'RED O/D (High Heat) | LUU480HHV.EWGBEUS', 'LG', 3049.89, 'und']]
        for division, sistema, desc, fab, precio, unidad in hvac_items:
            cur.execute(
                f"INSERT INTO catalog (id,division,sistema,descripcion,fab,precio,unidad,notas) VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})",
                (str(uuid.uuid4()), division, sistema, desc, fab, precio, unidad, 'Lista LG 2026')
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
