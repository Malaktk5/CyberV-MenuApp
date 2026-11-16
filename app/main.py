import os
from contextlib import asynccontextmanager
import psycopg2
from fastapi import FastAPI, Response, status
from fastapi.staticfiles import StaticFiles
from app import config
from app.routers import admin, auth, commandes, public
from app.seed import bootstrap


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        bootstrap()
    except Exception as e:  # la base peut ne pas être prête (tests, CI) : on ne bloque pas le démarrage
        print(f"[seed] ignoré : {e}")
    yield


app = FastAPI(title="CyberV Yummy API", lifespan=lifespan)


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


app.include_router(auth.router)
app.include_router(public.router)
app.include_router(commandes.router)
app.include_router(admin.router)
app.include_router(admin.staff)

config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=config.BASE_DIR / "frontend", html=True), name="frontend")  # toujours en dernier
