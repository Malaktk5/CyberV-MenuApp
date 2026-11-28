"""Tests for the kitchen screen API (/api/cuisine)."""


def test_kitchen_requires_cuisinier_role(anon, login_as):
    assert anon.get("/api/cuisine/commandes").status_code == 401
    serveur = login_as("serveur")
    assert serveur.get("/api/cuisine/commandes").status_code == 403


def test_kitchen_lists_active_orders_and_advances_status(login_as, make_order, get_order):
    cook = login_as("cuisinier")
    o1 = make_order(statut="recue", mode="sur_place")
    o2 = make_order(statut="en_preparation", mode="a_emporter")
    o3 = make_order(statut="prete", mode="sur_place")

    res = cook.get("/api/cuisine/commandes")
    assert res.status_code == 200
    ids = [o["id"] for o in res.json()]
    assert o1["id"] in ids and o2["id"] in ids
    assert o3["id"] not in ids
    assert ids.index(o1["id"]) < ids.index(o2["id"])

    # recue -> en_preparation
    r1 = cook.post(f"/api/cuisine/commandes/{o1['id']}/statut", json={"statut": "en_preparation"})
    assert r1.status_code == 200
    assert get_order(o1["id"])["statut"] == "en_preparation"

    # en_preparation -> prete
    r2 = cook.post(f"/api/cuisine/commandes/{o1['id']}/statut", json={"statut": "prete"})
    assert r2.status_code == 200
    assert get_order(o1["id"])["statut"] == "prete"

    # Invalid target status rejected
    r3 = cook.post(f"/api/cuisine/commandes/{o1['id']}/statut", json={"statut": "servie"})
    assert r3.status_code == 422
