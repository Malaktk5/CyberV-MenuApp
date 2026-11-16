import os
from datetime import timezone, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
TZ_HOURS = int(os.getenv("TZ_OFFSET_HOURS", "1"))  # Algérie : UTC+1, sans heure d'été
LOCAL_TZ = timezone(timedelta(hours=TZ_HOURS))
COOKIE = "yummy_session"
SESSION_HOURS = 8
DELIVERY_FEE = int(os.getenv("DELIVERY_FEE", "200"))  # DA
