import os
from contextlib import asynccontextmanager
import psycopg2
from fastapi import FastAPI, Response, status
from fastapi.staticfiles import StaticFiles
from app import config
from app.routers import admin, auth, commandes, public, ws
from app.seed import bootstrap


# Handles application startup and shutdown lifecycle events (e.g., seeding initial database data)
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        bootstrap()
    except Exception as e:  # la base peut ne pas être prête (tests, CI) : on ne bloque pas le démarrage
        print(f"[seed] ignoré : {e}")
    yield


app = FastAPI(title="CyberV Yummy API", lifespan=lifespan)


# Health check endpoint that verifies the API is running and can connect to PostgreSQL
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
app.include_router(ws.router)

config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=config.BASE_DIR / "frontend", html=True), name="frontend")  # toujours en dernier