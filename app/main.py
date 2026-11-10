import os
import psycopg2
from fastapi import FastAPI, Response, status

app = FastAPI(title="CyberV Yummy API")

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
