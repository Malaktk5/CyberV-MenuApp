from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from app import config
from app.db import cursor
from app.security import make_token, require_role, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Login(BaseModel):
    email: str
    mot_de_passe: str


@router.post("/login")
def login(body: Login, response: Response):
    with cursor() as cur:
        cur.execute("SELECT id, nom, prenom, role::text AS role, actif, mot_de_passe_hash FROM employes WHERE lower(email) = lower(%s)", (body.email.strip(),))
        u = cur.fetchone()
    if not u or not u["actif"] or not verify_password(body.mot_de_passe, u["mot_de_passe_hash"]):
        raise HTTPException(401, "Email ou mot de passe incorrect")
    response.set_cookie(config.COOKIE, make_token(u["id"]), max_age=config.SESSION_HOURS * 3600, httponly=True, samesite="lax")
    return {k: u[k] for k in ("id", "nom", "prenom", "role")}


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(config.COOKIE)


@router.get("/me")
def me(user=Depends(require_role())):
    return user
