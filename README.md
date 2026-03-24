# NEXUS · Ingesoft — Guía de Despliegue en Railway

## ¿Qué es esto?
NEXUS es tu herramienta de presupuestos con base de datos en la nube.
Una vez desplegada, tendrás una URL fija que funciona desde cualquier computador.

---

## Paso 1 — Crear cuenta en GitHub (gratis)
1. Ve a https://github.com y crea una cuenta si no tienes
2. Haz clic en "New repository"
3. Nómbralo `nexus-ingesoft`
4. Selecciona "Private" (para que sea privado)
5. Haz clic en "Create repository"

---

## Paso 2 — Subir los archivos a GitHub
En la página del repositorio vacío, haz clic en "uploading an existing file"
Sube estos archivos:
- main.py
- requirements.txt
- Procfile
- La carpeta `static/` con el archivo `index.html`

Haz clic en "Commit changes"

---

## Paso 3 — Crear cuenta en Railway (gratis)
1. Ve a https://railway.app
2. Haz clic en "Login with GitHub"
3. Autoriza Railway a acceder a tu cuenta de GitHub

---

## Paso 4 — Desplegar NEXUS
1. En Railway, haz clic en "New Project"
2. Selecciona "Deploy from GitHub repo"
3. Elige `nexus-ingesoft`
4. Railway detecta automáticamente que es una app Python
5. Haz clic en "Deploy Now"
6. Espera 2-3 minutos mientras Railway construye la app

---

## Paso 5 — Obtener tu URL
1. En el panel de Railway, haz clic en tu proyecto
2. Ve a "Settings" → "Networking" → "Generate Domain"
3. Railway te da una URL como: `nexus-ingesoft.up.railway.app`
4. ¡Listo! Comparte esa URL con tus colegas

---

## Uso diario
- Entra a tu URL desde cualquier navegador
- El catálogo y proyectos se guardan automáticamente en la base de datos
- Todos los usuarios del equipo ven el mismo catálogo actualizado

---

## Preguntas frecuentes

**¿Cuánto cuesta?**
Railway tiene un plan gratuito de $5 USD de crédito mensual.
Para 2-3 usuarios con uso normal, ese crédito alcanza todo el mes sin costo.

**¿Los datos están seguros?**
Sí. Railway usa servidores en AWS con backups automáticos.

**¿Qué pasa si necesito ayuda?**
Escríbeme y lo resuelvo.

---

## Estructura del proyecto
```
nexus_app/
├── main.py          → servidor backend (Python/FastAPI)
├── requirements.txt → librerías Python
├── Procfile         → instrucciones para Railway
└── static/
    └── index.html   → la app NEXUS completa
```
