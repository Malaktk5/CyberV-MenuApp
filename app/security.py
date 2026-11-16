import base64, hashlib, hmac, json, os, time
from fastapi import HTTPException, Request
from app import config
from app.db import cursor


def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1)
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


def _sign(payload: str) -> str:
    return hmac.new(config.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_token(employe_id: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"id": employe_id, "exp": int(time.time()) + config.SESSION_HOURS * 3600}).encode()).decode()
    return f"{payload}.{_sign(payload)}"


def read_token(token: str):
    try:
        payload, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data if data["exp"] > time.time() else None
    except Exception:
        return None


def require_role(*roles):
    """Dépendance FastAPI : exige une session valide et (optionnellement) un des rôles donnés."""
    def dep(request: Request):
        data = read_token(request.cookies.get(config.COOKIE, ""))
        if not data:
            raise HTTPException(401, "Non connecté")
        with cursor() as cur:
            cur.execute("SELECT id, nom, prenom, role::text AS role, actif FROM employes WHERE id = %s", (data["id"],))
            u = cur.fetchone()
        if not u or not u["actif"]:
            raise HTTPException(401, "Compte inconnu ou désactivé")
        if roles and u["role"] not in roles:
            raise HTTPException(403, "Accès refusé pour votre rôle")
        return u
    return dep
