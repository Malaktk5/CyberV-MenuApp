"""Tests that every staff role has the correct HTML page and JavaScript file."""
import re

import pytest

from app import config
from app.db import cursor

FRONTEND = config.BASE_DIR / "frontend"
SCREENS = {  # rôle -> (page, script)
    "cuisinier": ("/staff/cuisine.html", "/assets/js/staff/cuisine.js"),
    "serveur": ("/staff/salle.html", "/assets/js/staff/salle.js"),
    "caissier": ("/staff/caisse.html", "/assets/js/staff/caisse.js"),
    "livreur": ("/staff/livraison.html", "/assets/js/staff/livraison.js"),
}


def role_home():
    """Lit ROLE_HOME dans frontend/assets/js/shared/staff.js (la source unique des écrans d'accueil)."""
    src = (FRONTEND / "assets/js/shared/staff.js").read_text(encoding="utf-8")
    block = re.search(r"export const ROLE_HOME = \{(.*?)\};", src, re.S).group(1)
    return dict(re.findall(r"(\w+):\s*'([^']+)'", block))


@pytest.mark.parametrize("role,page_and_script", SCREENS.items())
def test_staff_page_and_script_are_served(role, page_and_script, anon):
    page, script = page_and_script
    r = anon.get(page)
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert f'src="{script}"' in r.text and "/assets/css/staff.css" in r.text and 'id="staff-root"' in r.text
    js = anon.get(script)
    assert js.status_code == 200
    assert f"staffPage('{role}'" in js.text  # chaque écran vérifie SON rôle


def test_shared_frame_files_are_served(anon):
    for path in ("/assets/js/shared/staff.js", "/assets/css/staff.css"):
        assert anon.get(path).status_code == 200


def test_every_role_has_a_home_that_exists():
    home = role_home()
    with cursor() as cur:
        cur.execute("SELECT unnest(enum_range(NULL::role_employe))::text AS role")
        roles_in_db = {r["role"] for r in cur.fetchall()}
    assert set(home) == roles_in_db, "un rôle de la base n'a pas d'écran d'accueil (ou l'inverse) dans ROLE_HOME"
    for role, url in home.items():
        target = FRONTEND / url.lstrip("/")
        assert (target / "index.html" if target.is_dir() or url.endswith("/") else target).is_file(), f"{role} : {url} n'existe pas"
    assert {r: home[r] for r in SCREENS} == {r: page for r, (page, _) in SCREENS.items()}


def test_login_page_sends_each_role_to_its_screen(anon):
    html = anon.get("/admin/login.html").text
    assert 'src="/assets/js/admin/login.js"' in html
    assert "cet espace sera bientôt disponible" not in html

    login_js = anon.get("/assets/js/admin/login.js").text
    assert "ROLE_HOME" in login_js
    assert "../shared/staff.js" in login_js

    staff_js = anon.get("/assets/js/shared/staff.js").text
    assert "ROLE_HOME" in staff_js


def test_cuisine_lists_active_orders_oldest_first(login_as, make_order):
    cook = login_as("cuisinier")
    older = make_order(statut="recue", mode="sur_place", created_at="2026-01-01 10:00:00+00")
    newer = make_order(statut="en_preparation", mode="a_emporter", created_at="2026-01-01 10:05:00+00")
    done = make_order(statut="prete", mode="sur_place", created_at="2026-01-01 09:50:00+00")

    r = cook.get("/api/cuisine/commandes")
    assert r.status_code == 200
    ids = [o["id"] for o in r.json()]
    assert older["id"] in ids and newer["id"] in ids
    assert done["id"] not in ids
    assert ids.index(older["id"]) < ids.index(newer["id"])


def test_cuisine_transitions_order_to_en_preparation_and_prete(login_as, make_order, get_order):
    cook = login_as("cuisinier")
    order = make_order(statut="recue", mode="sur_place")

    r1 = cook.post(f"/api/cuisine/commandes/{order['id']}/statut", json={"statut": "en_preparation"})
    assert r1.status_code == 200
    assert get_order(order["id"])["statut"] == "en_preparation"

    r2 = cook.post(f"/api/cuisine/commandes/{order['id']}/statut", json={"statut": "prete"})
    assert r2.status_code == 200
    assert get_order(order["id"])["statut"] == "prete"


def test_cuisine_rejects_invalid_status_or_wrong_role(login_as, make_order):
    order = make_order(statut="recue", mode="sur_place")
    waiter = login_as("serveur")
    assert waiter.get("/api/cuisine/commandes").status_code == 403

    cook = login_as("cuisinier")
    bad = cook.post(f"/api/cuisine/commandes/{order['id']}/statut", json={"statut": "terminee"})
    assert bad.status_code == 422
