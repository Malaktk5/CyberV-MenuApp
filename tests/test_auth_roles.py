"""Tests login, sessions, and role-based access to protected routes."""
import pytest

from app import config
from app.db import cursor
from app.security import make_token
from tests.conftest import PWD

ROLES = ["gerant", "cuisinier", "serveur", "caissier", "livreur"]
MISSING_ID = 999999999  # id de plat qui n'existe pas


# ---------------- A. Authentification ----------------
def test_login_success_returns_user_and_cookie(anon, make_employe):
    e = make_employe("cuisinier")
    r = anon.post("/api/auth/login", json={"email": e["email"], "mot_de_passe": PWD})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"id", "nom", "prenom", "role"}  # pas de hash dans la réponse
    assert body["id"] == e["id"] and body["role"] == "cuisinier"
    cookie = r.headers["set-cookie"].lower()
    assert config.COOKIE in cookie and "httponly" in cookie


def test_login_email_is_case_and_space_insensitive(anon, make_employe):
    email = make_employe("serveur")["email"]
    r = anon.post("/api/auth/login", json={"email": f"  {email.upper()}  ", "mot_de_passe": PWD})
    assert r.status_code == 200


def test_login_wrong_password_and_unknown_email_give_same_error(anon, make_employe):
    email = make_employe("serveur")["email"]
    c = anon
    r1 = c.post("/api/auth/login", json={"email": email, "mot_de_passe": "mauvais"})
    r2 = c.post("/api/auth/login", json={"email": "inconnu@test.local", "mot_de_passe": PWD})
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json() == {"detail": "Email ou mot de passe incorrect"}
    assert config.COOKIE not in r1.headers.get("set-cookie", "")


def test_login_inactive_account_refused(anon, make_employe):
    email = make_employe("serveur", actif=False)["email"]
    r = anon.post("/api/auth/login", json={"email": email, "mot_de_passe": PWD})
    assert r.status_code == 401


@pytest.mark.parametrize("payload", [{}, {"email": "a@b.c"}, {"mot_de_passe": "x"}, {"email": 1, "mot_de_passe": None}])
def test_login_invalid_payload_returns_422(anon, payload):
    assert anon.post("/api/auth/login", json=payload).status_code == 422


def test_me_requires_session(anon):
    r = anon.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["detail"] == "Non connecté"


def test_me_returns_current_user(login_as):
    c = login_as("caissier")
    r = c.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["id"] == c.employe["id"] and r.json()["role"] == "caissier"
    assert "mot_de_passe_hash" not in r.json()


def test_logout_ends_session(login_as):
    c = login_as("gerant")
    assert c.get("/api/auth/me").status_code == 200
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 401


def test_garbage_and_tampered_tokens_are_refused(anon, make_employe):
    token = make_token(make_employe("gerant")["id"])
    payload, sig = token.split(".")
    for bad in ("n-importe-quoi", f"{payload}.{'0' * len(sig)}", f"{payload}x.{sig}", ""):
        c = anon
        c.cookies.set(config.COOKIE, bad)
        assert c.get("/api/auth/me").status_code == 401


def test_expired_token_is_refused(anon, make_employe, monkeypatch):
    eid = make_employe("gerant")["id"]
    monkeypatch.setattr(config, "SESSION_HOURS", -1)  # le token créé est déjà expiré
    expired = make_token(eid)
    c = anon
    c.cookies.set(config.COOKIE, expired)
    assert c.get("/api/auth/me").status_code == 401


def test_token_of_deactivated_user_is_refused(login_as):
    c = login_as("serveur")
    assert c.get("/api/auth/me").status_code == 200
    with cursor() as cur:
        cur.execute("UPDATE employes SET actif = FALSE WHERE id = %s", (c.employe["id"],))
    r = c.get("/api/auth/me")
    assert r.status_code == 401 and "désactivé" in r.json()["detail"]


# ---------------- B. Rôles et routes protégées ----------------
@pytest.mark.parametrize("role", ROLES)
def test_me_works_for_every_role(role, login_as):
    c = login_as(role)
    r = c.get("/api/auth/me")
    assert r.status_code == 200 and r.json()["role"] == role


@pytest.mark.parametrize("role", ROLES)
def test_admin_area_is_reserved_to_gerant(role, login_as):
    c = login_as(role)
    expected = 200 if role == "gerant" else 403
    assert c.get("/api/admin/plats").status_code == expected
    assert c.get("/api/admin/employes").status_code == expected
    if role != "gerant":
        assert c.get("/api/admin/plats").json()["detail"] == "Accès refusé pour votre rôle"


@pytest.mark.parametrize("role", ROLES)
def test_staff_availability_allowed_for_gerant_and_cuisinier_only(role, login_as):
    c = login_as(role)
    r = c.patch(f"/api/staff/plats/{MISSING_ID}/disponibilite", json={"disponible": False})
    # autorisé -> la route s'exécute et répond 404 (plat inexistant) ; sinon 403
    assert r.status_code == (404 if role in ("gerant", "cuisinier") else 403)


@pytest.mark.parametrize("method,url,body", [
    ("get", "/api/admin/plats", None),
    ("get", "/api/admin/categories", None),
    ("get", "/api/admin/employes", None),
    ("get", "/api/admin/stats", None),
    ("get", "/api/admin/commandes", None),
    ("get", "/api/admin/commandes/resume", None),
    ("post", "/api/admin/plats", {"categorie_id": 1, "nom": "X", "prix": 1}),
    ("put", f"/api/admin/plats/{MISSING_ID}", {"categorie_id": 1, "nom": "X", "prix": 1}),
    ("delete", f"/api/admin/plats/{MISSING_ID}", None),
    ("patch", f"/api/staff/plats/{MISSING_ID}/disponibilite", {"disponible": True}),
])
def test_protected_routes_return_401_without_session(anon, method, url, body):
    r = anon.request(method, url, json=body)
    assert r.status_code == 401


def test_non_gerant_cannot_write_menu(login_as):
    c = login_as("serveur")
    assert c.post("/api/admin/plats", json={"categorie_id": 1, "nom": "ZZ_TEST_X", "prix": 1}).status_code == 403
    assert c.delete(f"/api/admin/plats/{MISSING_ID}").status_code == 403


def test_public_menu_needs_no_login(anon):
    r = anon.get("/api/menu")
    assert r.status_code == 200 and isinstance(r.json(), list)
