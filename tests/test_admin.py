"""Tests admin login, menu management, availability, employees, statistics, and uploads."""
import base64
import uuid

from app import config
from app.db import cursor
from app.security import hash_password, verify_password

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")

def test_password_hash_roundtrip():
    h = hash_password("abc12345")
    assert verify_password("abc12345", h) and not verify_password("autre", h)


def test_admin_routes_require_login(anon):
    for url in ("/api/admin/stats", "/api/admin/plats", "/api/admin/categories", "/api/admin/employes"):
        assert anon.get(url).status_code == 401


def test_bad_login_and_wrong_role(anon, login_as):
    assert anon.post("/api/auth/login", json={"email": "nobody@test.local", "mot_de_passe": "x"}).status_code == 401
    assert login_as("serveur").get("/api/admin/stats").status_code == 403


def test_plat_crud_availability_archive(admin):
    cat = admin.post("/api/admin/categories", json={"nom": "ZZ_TEST_Cat", "ordre": 99}).json()
    p = admin.post("/api/admin/plats", json={"categorie_id": cat["id"], "nom": "ZZ_TEST_Plat", "prix": 500, "temps_preparation": 7}).json()
    assert p["disponible"] is True and p["prix"] == 500

    p = admin.put(f"/api/admin/plats/{p['id']}", json={"categorie_id": cat["id"], "nom": "ZZ_TEST_Plat", "prix": 650, "description": "ok"}).json()
    assert p["prix"] == 650

    # case décochée -> plat indisponible, mais toujours visible (grisé) dans le menu public
    assert admin.patch(f"/api/staff/plats/{p['id']}/disponibilite", json={"disponible": False}).json()["disponible"] is False
    menu = {pl["id"]: pl for c in admin.get("/api/menu").json() for pl in c["plats"]}
    assert menu[p["id"]]["disponible"] is False

    # archivage -> disparaît du menu public, restaurable
    admin.post(f"/api/admin/plats/{p['id']}/archiver")
    assert p["id"] not in {pl["id"] for c in admin.get("/api/menu").json() for pl in c["plats"]}
    assert p["id"] in {x["id"] for x in admin.get("/api/admin/plats?archives=true").json()}
    assert p["id"] not in {x["id"] for x in admin.get("/api/admin/plats").json()}
    assert admin.post(f"/api/admin/plats/{p['id']}/restaurer").json()["archive"] is False

    assert admin.delete(f"/api/admin/plats/{p['id']}").status_code == 204
    assert admin.delete(f"/api/admin/categories/{cat['id']}").status_code == 204


def test_category_rules(admin):
    cat = admin.post("/api/admin/categories", json={"nom": "ZZ_TEST_Dup"}).json()
    assert admin.post("/api/admin/categories", json={"nom": "ZZ_TEST_Dup"}).status_code == 409
    admin.post("/api/admin/plats", json={"categorie_id": cat["id"], "nom": "ZZ_TEST_P", "prix": 1})
    assert admin.delete(f"/api/admin/categories/{cat['id']}").status_code == 409  # catégorie non vide
    assert admin.post("/api/admin/plats", json={"categorie_id": 999999, "nom": "ZZ_TEST_X", "prix": 1}).status_code == 422
    assert admin.post("/api/admin/plats", json={"categorie_id": cat["id"], "nom": "ZZ_TEST_Y", "prix": -5}).status_code == 422


def test_kitchen_can_toggle_availability_but_not_admin(admin, login_as):
    cat = admin.post("/api/admin/categories", json={"nom": "ZZ_TEST_K"}).json()
    p = admin.post("/api/admin/plats", json={"categorie_id": cat["id"], "nom": "ZZ_TEST_Kp", "prix": 10}).json()
    cuisinier = login_as("cuisinier")
    assert cuisinier.patch(f"/api/staff/plats/{p['id']}/disponibilite", json={"disponible": False}).status_code == 200
    assert cuisinier.post("/api/admin/plats", json={"categorie_id": cat["id"], "nom": "ZZ_TEST_Z", "prix": 1}).status_code == 403
    assert login_as("serveur").patch(f"/api/staff/plats/{p['id']}/disponibilite", json={"disponible": True}).status_code == 403


def test_stats_shape(admin):
    for period in ("day", "week", "month", "year"):
        s = admin.get(f"/api/admin/stats?period={period}").json()
        for key in ("ca", "commandes", "panier_moyen", "plats_vendus", "top_plats", "heures_de_pointe", "serie", "en_cours", "modes"):
            assert key in s
    assert admin.get("/api/admin/stats?period=decade").status_code == 422


def test_employees(admin, anon):
    email = f"test-{uuid.uuid4().hex[:8]}@test.local"
    body = {"nom": "A", "prenom": "B", "email": email, "mot_de_passe": "motdepasse1", "role": "livreur"}
    e = admin.post("/api/admin/employes", json=body).json()
    assert e["role"] == "livreur"
    assert admin.post("/api/admin/employes", json=body).status_code == 409
    assert admin.post("/api/admin/employes", json={**body, "email": "pasunemail"}).status_code == 422
    assert admin.patch(f"/api/admin/employes/{e['id']}", json={"actif": False}).json()["actif"] is False
    # un compte désactivé ne peut plus se connecter
    assert anon.post("/api/auth/login", json={"email": email, "mot_de_passe": "motdepasse1"}).status_code == 401
    me = admin.get("/api/auth/me").json()
    assert admin.patch(f"/api/admin/employes/{me['id']}", json={"actif": False}).status_code == 409


def test_upload(admin):
    assert admin.post("/api/admin/upload", content=b"pas une image").status_code == 400
    r = admin.post("/api/admin/upload", content=PNG, headers={"content-type": "image/png"})
    assert r.status_code == 201 and r.json()["url"].startswith("/uploads/")
    assert admin.get(r.json()["url"]).status_code == 200
    (config.UPLOAD_DIR / r.json()["url"].split("/")[-1]).unlink()
    assert admin.post("/api/admin/plats", json={"categorie_id": 1, "nom": "ZZ_TEST_J", "prix": 1, "photo_url": "javascript:alert(1)"}).status_code == 422


def test_frontend_pages_served(anon):
    home = anon.get("/")
    assert home.status_code == 200 and "Notre menu" in home.text
    assert anon.get("/admin/login.html").status_code == 200 and anon.get("/admin/").status_code == 200
    assert anon.get("/assets/js/admin/plats.js").status_code == 200


def test_menu_seed_is_idempotent_and_adds_photos():
    from app.seed import seed_menu
    with cursor() as cur:
        cur.execute("SELECT id, photo_url FROM plats")
        before = {r["id"]: r["photo_url"] for r in cur.fetchall()}
    try:
        seed_menu(); seed_menu()
        with cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM plats"); n1 = cur.fetchone()["n"]
        seed_menu()
        with cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM plats"); assert cur.fetchone()["n"] == n1  # pas de doublons
            cur.execute("SELECT photo_url FROM plats WHERE nom = 'Couscous'")
            assert cur.fetchone()["photo_url"].startswith("/assets/img/menu/")
    finally:  # on remet la base de test dans son état initial
        with cursor() as cur:
            cur.execute("DELETE FROM plats WHERE id <> ALL(%s)", (list(before),))
            for pid, url in before.items():
                cur.execute("UPDATE plats SET photo_url = %s WHERE id = %s", (url, pid))


def test_site_images_and_site_photo_url(admin, anon):
    for path in ("/assets/img/logo.png", "/assets/img/menu/tajine.jpg", "/assets/img/about/chef.jpg"):
        assert anon.get(path).status_code == 200
    cat = admin.post("/api/admin/categories", json={"nom": "ZZ_TEST_Img"}).json()
    r = admin.post("/api/admin/plats", json={"categorie_id": cat["id"], "nom": "ZZ_TEST_Photo", "prix": 1, "photo_url": "/assets/img/menu/1.jpg"})
    assert r.status_code == 201
