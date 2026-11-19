"""Tests the complete order flow from the customer to the manager."""
import uuid

import pytest

from app.db import cursor
from app.routers import commandes as cmd_module

NOTE = "ZZ_TEST_note"  # le préfixe ZZ_TEST_ permet le nettoyage automatique (tests/conftest.py)


@pytest.fixture
def plat(admin):
    g = admin
    cat = g.post("/api/admin/categories", json={"nom": "ZZ_TEST_Cmd"}).json()
    p = g.post("/api/admin/plats", json={"categorie_id": cat["id"], "nom": "ZZ_TEST_Plat", "prix": 500}).json()
    return g, p


def order(c, p, **kw):
    body = {"mode": "sur_place", "table_numero": 1, "note": NOTE, "lignes": [{"plat_id": p["id"], "quantite": 2, "commentaire": "sans oignons"}], **kw}
    return c.post("/api/commandes", json=body)


def test_options(anon):
    o = anon.get("/api/options-commande").json()
    assert o["frais_livraison"] == 200 and 1 in o["tables"]


def test_dine_in_order_and_manager_receives_it(plat, anon):
    g, p = plat
    c = anon  # le client n'a pas de compte
    r = order(c, p)
    assert r.status_code == 201
    d = r.json()
    assert d["numero"].startswith("CMD-") and d["total"] == 1000 and d["statut"] == "recue" and d["paiement_statut"] == "en_attente"
    # le gérant la voit dans « Commandes » avec la note et le commentaire de ligne
    liste = {o["numero"]: o for o in g.get("/api/admin/commandes?statut=encours").json()}
    o = liste[d["numero"]]
    assert o["note"] == NOTE and o["table_numero"] == 1 and o["lignes"][0]["commentaire"] == "sans oignons" and o["lignes"][0]["quantite"] == 2
    assert g.get("/api/admin/commandes/resume").json()["recues"] >= 1
    assert d["numero"] in {x["numero"] for x in g.get(f"/api/admin/commandes?statut=toutes&q={d['numero']}").json()}


def test_delivery_fee_and_card_payment_is_simulated(plat, anon):
    _, p = plat
    c = anon
    d = order(c, p, mode="livraison", table_numero=None, client_nom="Sara", client_telephone="0550 12 34 56",
              adresse_livraison="12 rue des Roses", paiement_mode="en_ligne").json()
    assert d["frais_livraison"] == 200 and d["total"] == 1200 and d["paiement_statut"] == "paye"
    with cursor() as cur:  # aucune donnée de carte dans la base : seules ces colonnes existent
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'commandes'")
        assert not [r for r in cur.fetchall() if "carte" in r["column_name"] or "cvc" in r["column_name"]]


def test_validation_rules(plat, anon):
    _, p = plat
    c = anon
    assert order(c, p, table_numero=None).status_code == 422                                   # table obligatoire
    assert order(c, p, table_numero=999).status_code == 422                                    # table inconnue
    assert order(c, p, mode="a_emporter", table_numero=None).status_code == 422                # nom + téléphone
    assert order(c, p, mode="livraison", table_numero=None, client_nom="A", client_telephone="0550123456").status_code == 422  # adresse
    assert order(c, p, mode="a_emporter", table_numero=None, client_nom="A", client_telephone="abc").status_code == 422
    assert c.post("/api/commandes", json={"mode": "sur_place", "table_numero": 1, "lignes": []}).status_code == 422
    assert c.post("/api/commandes", json={"mode": "sur_place", "table_numero": 1, "lignes": [{"plat_id": p["id"], "quantite": 0}]}).status_code == 422
    assert c.post("/api/commandes", json={"mode": "sur_place", "table_numero": 1, "lignes": [{"plat_id": 99999999, "quantite": 1}]}).status_code == 409


def test_unavailable_and_archived_dishes_are_refused(plat, anon):
    g, p = plat
    c = anon
    g.patch(f"/api/staff/plats/{p['id']}/disponibilite", json={"disponible": False})
    r = order(c, p)
    assert r.status_code == 409 and "plus disponible" in r.json()["detail"]
    g.patch(f"/api/staff/plats/{p['id']}/disponibilite", json={"disponible": True})
    g.post(f"/api/admin/plats/{p['id']}/archiver")
    assert order(c, p).status_code == 409


def test_prices_come_from_database_not_from_client(plat, anon):
    _, p = plat
    r = anon.post("/api/commandes", json={"mode": "sur_place", "table_numero": 1, "note": NOTE, "prix": 1, "total": 1,
                                                      "lignes": [{"plat_id": p["id"], "quantite": 1, "prix": 1}]})
    assert r.status_code == 201 and r.json()["total"] == 500


def test_tracking_by_token(plat, anon):
    _, p = plat
    c = anon
    d = order(c, p).json()
    s = c.get(f"/api/commandes/suivi/{d['suivi_token']}").json()
    assert s["statut"] == "recue" and s["total"] == 1000 and s["lignes"][0]["nom"] == "ZZ_TEST_Plat" and "client_telephone" not in s
    assert c.get("/api/commandes/suivi/pas-un-uuid").status_code == 404
    assert c.get(f"/api/commandes/suivi/{uuid.uuid4()}").status_code == 404


def test_admin_orders_require_manager(anon, login_as):
    assert anon.get("/api/admin/commandes").status_code == 401
    assert login_as("serveur").get("/api/admin/commandes").status_code == 403


def test_manager_cancel_rules(plat, anon, make_order, get_order, get_history):
    g, p = plat
    c = anon
    paid = order(c, p, paiement_mode="en_ligne").json()
    paid_id = get_order(paid["numero"])["id"]
    r = g.post(f"/api/admin/commandes/{paid_id}/annuler")
    assert r.status_code == 200
    assert r.json()["statut"] == "annulee"
    assert r.json()["paiement_statut"] == "rembourse"
    assert g.post(f"/api/admin/commandes/{paid_id}/annuler").status_code == 409
    assert g.post("/api/admin/commandes/99999999/annuler").status_code == 404
    assert c.get(f"/api/commandes/suivi/{paid['suivi_token']}").json()["statut"] == "annulee"
    assert get_history(paid_id)[-1]["nouveau_statut"] == "annulee"

    d = make_order(statut="en_preparation")
    assert g.post(f"/api/admin/commandes/{d['id']}/annuler").status_code == 409
