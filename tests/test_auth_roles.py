"""Tests d'authentification et de contrôle d'accès par rôle """
import uuid

import pytest
from fastapi.testclient import TestClient

from app import config
from app.db import cursor
from app.main import app
from app.security import hash_password, make_token

PWD = "Secret123!"
ROLES = ["gerant", "cuisinier", "serveur", "caissier", "livreur"]
PREFIX = "authtest-"
MISSING_ID = 999999999  # id de plat qui n'existe pas


def create_employe(role="gerant", actif=True):
    """Crée un employé de test directement en base et renvoie (email, id)."""
    email = f"{PREFIX}{uuid.uuid4().hex[:8]}@test.local"
    with cursor() as cur:
        cur.execute(
            """INSERT INTO employes (nom, prenom, email, mot_de_passe_hash, role, actif)
               VALUES ('Test', %s, %s, %s, %s, %s) RETURNING id""",
            (role, email, hash_password(PWD), role, actif),
        )
        return email, cur.fetchone()["id"]


def logged_client(role="gerant"):
    """Renvoie un client déjà connecté avec ce rôle, et l'id de l'employé."""
    email, eid = create_employe(role)
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "mot_de_passe": PWD})
    assert r.status_code == 200
    return c, eid


@pytest.fixture(autouse=True)
def cleanup():
    yield
    with cursor() as cur:
        cur.execute("DELETE FROM employes WHERE email LIKE %s", (PREFIX + "%@test.local",))


# ---------------- A. Authentification ----------------
def test_login_success_returns_user_and_cookie():
    email, eid = create_employe("cuisinier")
    r = TestClient(app).post("/api/auth/login", json={"email": email, "mot_de_passe": PWD})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"id", "nom", "prenom", "role"}  # pas de hash dans la réponse
    assert body["id"] == eid and body["role"] == "cuisinier"
    cookie = r.headers["set-cookie"].lower()
    assert config.COOKIE in cookie and "httponly" in cookie


def test_login_email_is_case_and_space_insensitive():
    email, _ = create_employe("serveur")
    r = TestClient(app).post("/api/auth/login", json={"email": f"  {email.upper()}  ", "mot_de_passe": PWD})
    assert r.status_code == 200


def test_login_wrong_password_and_unknown_email_give_same_error():
    email, _ = create_employe("serveur")
    c = TestClient(app)
    r1 = c.post("/api/auth/login", json={"email": email, "mot_de_passe": "mauvais"})
    r2 = c.post("/api/auth/login", json={"email": "inconnu@test.local", "mot_de_passe": PWD})
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json() == {"detail": "Email ou mot de passe incorrect"}
    assert config.COOKIE not in r1.headers.get("set-cookie", "")


def test_login_inactive_account_refused():
    email, _ = create_employe("serveur", actif=False)
    r = TestClient(app).post("/api/auth/login", json={"email": email, "mot_de_passe": PWD})
    assert r.status_code == 401


@pytest.mark.parametrize("payload", [{}, {"email": "a@b.c"}, {"mot_de_passe": "x"}, {"email": 1, "mot_de_passe": None}])
def test_login_invalid_payload_returns_422(payload):
    assert TestClient(app).post("/api/auth/login", json=payload).status_code == 422


def test_me_requires_session():
    r = TestClient(app).get("/api/auth/me")
    assert r.status_code == 401 and r.json()["detail"] == "Non connecté"


def test_me_returns_current_user():
    c, eid = logged_client("caissier")
    r = c.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["id"] == eid and r.json()["role"] == "caissier"
    assert "mot_de_passe_hash" not in r.json()


def test_logout_ends_session():
    c, _ = logged_client("gerant")
    assert c.get("/api/auth/me").status_code == 200
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 401


def test_garbage_and_tampered_tokens_are_refused():
    _, eid = logged_client("gerant")
    token = make_token(eid)
    payload, sig = token.split(".")
    for bad in ("n-importe-quoi", f"{payload}.{'0' * len(sig)}", f"{payload}x.{sig}", ""):
        c = TestClient(app)
        c.cookies.set(config.COOKIE, bad)
        assert c.get("/api/auth/me").status_code == 401


def test_expired_token_is_refused(monkeypatch):
    _, eid = create_employe("gerant")
    monkeypatch.setattr(config, "SESSION_HOURS", -1)  # le token créé est déjà expiré
    expired = make_token(eid)
    c = TestClient(app)
    c.cookies.set(config.COOKIE, expired)
    assert c.get("/api/auth/me").status_code == 401


def test_token_of_deactivated_user_is_refused():
    c, eid = logged_client("serveur")
    assert c.get("/api/auth/me").status_code == 200
    with cursor() as cur:
        cur.execute("UPDATE employes SET actif = FALSE WHERE id = %s", (eid,))
    r = c.get("/api/auth/me")
    assert r.status_code == 401 and "désactivé" in r.json()["detail"]


# ---------------- B. Rôles et routes protégées ----------------
@pytest.mark.parametrize("role", ROLES)
def test_me_works_for_every_role(role):
    c, _ = logged_client(role)
    r = c.get("/api/auth/me")
    assert r.status_code == 200 and r.json()["role"] == role


@pytest.mark.parametrize("role", ROLES)
def test_admin_area_is_reserved_to_gerant(role):
    c, _ = logged_client(role)
    expected = 200 if role == "gerant" else 403
    assert c.get("/api/admin/plats").status_code == expected
    assert c.get("/api/admin/employes").status_code == expected
    if role != "gerant":
        assert c.get("/api/admin/plats").json()["detail"] == "Accès refusé pour votre rôle"


@pytest.mark.parametrize("role", ROLES)
def test_staff_availability_allowed_for_gerant_and_cuisinier_only(role):
    c, _ = logged_client(role)
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
def test_protected_routes_return_401_without_session(method, url, body):
    r = TestClient(app).request(method, url, json=body)
    assert r.status_code == 401


def test_non_gerant_cannot_write_menu():
    c, _ = logged_client("serveur")
    assert c.post("/api/admin/plats", json={"categorie_id": 1, "nom": "ZZ_TEST_X", "prix": 1}).status_code == 403
    assert c.delete(f"/api/admin/plats/{MISSING_ID}").status_code == 403


def test_public_menu_needs_no_login():
    r = TestClient(app).get("/api/menu")
    assert r.status_code == 200 and isinstance(r.json(), list)