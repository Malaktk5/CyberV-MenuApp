import os
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor


def dsn() -> str:
    return os.getenv("DATABASE_URL", "postgresql://yummy_user:yummy_password@db:5432/yummy_db")


@contextmanager
def cursor():
    """Une transaction : commit si tout va bien, rollback si une exception survient."""
    conn = psycopg2.connect(dsn(), cursor_factory=RealDictCursor)
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()
