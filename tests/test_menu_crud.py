"""Tests menu item creation, reading, updates, archiving, deletion, and validation."""
import uuid

import pytest

PREFIX = "ZZ_TEST_MENU_"  # commence par ZZ_TEST_ : nettoyé automatiquement (tests/conftest.py)
MISSING_ID = 999999999
PLAT_KEYS = {"id", "nom", "prix", "disponible", "archive"}


@pytest.fixture
def cat(admin):
    r = admin.post("/api/admin/categories", json={"nom": f"{PREFIX}Cat_{uuid.uuid4().hex[:6]}", "ordre": 99})
    assert r.status_code == 201
    return r.json()


def body(cat, **over):
    base = {"categorie_id": cat["id"], "nom": f"{PREFIX}Plat_{uuid.uuid4().hex[:6]}", "prix": 500, "temps_preparation": 7}
    base.update(over)
    return base


# ---------------- CREATE ----------------
def test_create_plat_returns_201_and_expected_structure(admin, cat):
    payload = body(cat, description="Délicieux")
    r = admin.post("/api/admin/plats", json=payload)
    assert r.status_code == 201
    p = r.json()
    assert PLAT_KEYS <= set(p)
    assert isinstance(p["id"], int)
    assert p["nom"] == payload["nom"] and p["prix"] == 500
    assert p["disponible"] is True and p["archive"] is False


def test_create_plat_trims_name(admin, cat):
    name = f"{PREFIX}Trim_{uuid.uuid4().hex[:6]}"
    r = admin.post("/api/admin/plats", json=body(cat, nom=f"   {name}   "))
    assert r.status_code == 201 and r.json()["nom"] == name


def test_create_plat_accepts_valid_photo_urls(admin, cat):
    for url in ("/assets/img/menu/1.jpg", "https://exemple.com/a.jpg"):
        assert admin.post("/api/admin/plats", json=body(cat, photo_url=url)).status_code == 201


@pytest.mark.parametrize("over", [
    {"nom": ""},                           # nom vide
    {"nom": "x" * 151},                    # nom trop long
    {"prix": -1},                          # prix négatif
    {"prix": "beaucoup"},                  # mauvais type
    {"temps_preparation": -3},             # durée négative
    {"photo_url": "javascript:alert(1)"},  # URL refusée par le validateur
    {"categorie_id": "abc"},               # mauvais type
])
def test_create_plat_invalid_data_returns_422(admin, cat, over):
    r = admin.post("/api/admin/plats", json=body(cat, **over))
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list)  # format d'erreur de validation FastAPI


@pytest.mark.parametrize("missing", ["categorie_id", "nom", "prix"])
def test_create_plat_missing_required_field_returns_422(admin, cat, missing):
    payload = body(cat)
    del payload[missing]
    assert admin.post("/api/admin/plats", json=payload).status_code == 422


def test_create_plat_unknown_category_returns_422(admin, cat):
    r = admin.post("/api/admin/plats", json=body(cat, categorie_id=MISSING_ID))
    assert r.status_code == 422 and r.json()["detail"] == "Catégorie inconnue"


# ---------------- READ ----------------
def test_admin_list_contains_created_plat(admin, cat):
    p = admin.post("/api/admin/plats", json=body(cat)).json()
    r = admin.get("/api/admin/plats")
    assert r.status_code == 200 and isinstance(r.json(), list)
    found = next(x for x in r.json() if x["id"] == p["id"])
    assert PLAT_KEYS <= set(found)


def test_public_menu_structure_and_content(admin, anon, cat):
    p = admin.post("/api/admin/plats", json=body(cat)).json()
    r = anon.get("/api/menu")
    assert r.status_code == 200
    categories = r.json()
    assert categories and all({"id", "nom", "plats"} <= set(c) for c in categories)
    assert all(c["plats"] for c in categories)  # les catégories vides ne sont pas renvoyées
    mine = next(c for c in categories if c["id"] == cat["id"])
    plat = next(x for x in mine["plats"] if x["id"] == p["id"])
    assert set(plat) == {"id", "nom", "description", "prix", "photo_url", "temps_preparation", "disponible"}
    assert isinstance(plat["prix"], float)


def test_empty_category_is_not_in_public_menu(anon, cat):
    ids = {c["id"] for c in anon.get("/api/menu").json()}
    assert cat["id"] not in ids


# ---------------- UPDATE ----------------
def test_update_plat_changes_fields(admin, cat):
    p = admin.post("/api/admin/plats", json=body(cat)).json()
    r = admin.put(f"/api/admin/plats/{p['id']}", json=body(cat, nom=p["nom"], prix=750, description="Nouveau", disponible=False))
    assert r.status_code == 200
    u = r.json()
    assert u["id"] == p["id"] and u["prix"] == 750 and u["disponible"] is False
    # la modification est bien persistée
    listed = next(x for x in admin.get("/api/admin/plats").json() if x["id"] == p["id"])
    assert listed["prix"] == 750


def test_update_unknown_plat_returns_404(admin, cat):
    r = admin.put(f"/api/admin/plats/{MISSING_ID}", json=body(cat))
    assert r.status_code == 404 and r.json()["detail"] == "Plat introuvable"


def test_update_plat_invalid_data_returns_422(admin, cat):
    p = admin.post("/api/admin/plats", json=body(cat)).json()
    assert admin.put(f"/api/admin/plats/{p['id']}", json=body(cat, prix=-10)).status_code == 422
    assert admin.put(f"/api/admin/plats/{p['id']}", json=body(cat, categorie_id=MISSING_ID)).status_code == 422
    # le plat n'a pas été modifié
    assert next(x for x in admin.get("/api/admin/plats").json() if x["id"] == p["id"])["prix"] == 500


def test_update_with_non_integer_id_returns_422(admin, cat):
    assert admin.put("/api/admin/plats/abc", json=body(cat)).status_code == 422


# ---------------- ARCHIVE / RESTORE ----------------
def test_archive_and_restore_unknown_plat_return_404(admin):
    assert admin.post(f"/api/admin/plats/{MISSING_ID}/archiver").status_code == 404
    assert admin.post(f"/api/admin/plats/{MISSING_ID}/restaurer").status_code == 404


# ---------------- DELETE ----------------
def test_delete_plat_returns_204_then_404(admin, cat):
    p = admin.post("/api/admin/plats", json=body(cat)).json()
    r = admin.delete(f"/api/admin/plats/{p['id']}")
    assert r.status_code == 204 and r.content == b""
    assert p["id"] not in {x["id"] for x in admin.get("/api/admin/plats?archives=true").json()}
    again = admin.delete(f"/api/admin/plats/{p['id']}")
    assert again.status_code == 404 and again.json()["detail"] == "Plat introuvable"


def test_delete_unknown_plat_returns_404(admin):
    assert admin.delete(f"/api/admin/plats/{MISSING_ID}").status_code == 404


def test_delete_already_ordered_plat_returns_409_and_can_be_archived(admin, anon, cat, make_order):
    p = admin.post("/api/admin/plats", json=body(cat)).json()
    make_order(plat=p, mode="a_emporter")  # une commande réelle référence ce plat
    r = admin.delete(f"/api/admin/plats/{p['id']}")
    assert r.status_code == 409 and "archivez-le" in r.json()["detail"]
    # le plat existe toujours, et l'archivage est l'alternative proposée
    assert p["id"] in {x["id"] for x in admin.get("/api/admin/plats").json()}
    assert admin.post(f"/api/admin/plats/{p['id']}/archiver").json()["archive"] is True
    assert p["id"] not in {pl["id"] for c in anon.get("/api/menu").json() for pl in c["plats"]}
