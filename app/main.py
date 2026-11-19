import os
from contextlib import asynccontextmanager
import psycopg2
from fastapi import FastAPI, Response, status
from fastapi.staticfiles import StaticFiles
from app import config
from app.routers import admin, auth, caisse, commandes, cuisine, dispatch, livraison, public, qr, salle, suivi, ws
from app.seed import bootstrap


# Run database setup when the application starts. Seed failures are reported but do not stop startup.
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        bootstrap()
    except Exception as e:  # la base peut ne pas être prête (tests, CI) : on ne bloque pas le démarrage
        print(f"[seed] ignoré : {e}")
    yield


app = FastAPI(title="CyberV Yummy API", lifespan=lifespan)


# Check whether both the API and PostgreSQL are available.
@app.get("/health")
def health_check(response: Response):
    db_url = os.getenv("DATABASE_URL", "postgresql://yummy_user:yummy_password@db:5432/yummy_db")
    try:
        conn = psycopg2.connect(db_url)
        conn.close()
        return {"status": "OK", "database": "connected"}
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "ERROR", "database": str(e)}


# Central router registration. Discuss any router change with the team before editing this section.
ROUTERS = (
    auth.router, public.router, commandes.router, admin.router, admin.staff, ws.router,
    suivi.router,      # F1  suivi client, annulation, temps d'attente
    cuisine.router,    # F2  écran cuisine
    salle.router,      # F3  écran salle
    caisse.router,     # F4  caisse
    dispatch.router,   # F5  affectation des livraisons (page de la caisse)
    livraison.router,  # F6  écran livreur
    qr.router,         # F11 QR codes des tables
)
for r in ROUTERS:
    app.include_router(r)

config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=config.BASE_DIR / "frontend", html=True), name="frontend")  # toujours en dernier
