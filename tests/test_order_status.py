"""Tests order status rules, permissions, history, timestamps, and concurrent updates."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException

from app.db import cursor
from app.order_status import CLIENT, TRANSITIONS, change_status

ROLES = ["cuisinier", "serveur", "caissier", "livreur", "gerant", "client"]

# Fixed specification: changes to `TRANSITIONS` must be intentional and reflected in this test.
SPEC = {
    "cuisinier": {("recue", "en_preparation"), ("en_preparation", "prete")},
    "serveur": {("prete", "servie")},
    "livreur": {("prete", "en_route"), ("en_route", "livree"), ("en_route", "echec")},
    "caissier": {("recue", "annulee")},
    "client": {("recue", "annulee")},
    "gerant": set(),
}


@pytest.fixture
def who(make_employe):
    """who("cuisinier") -> (appelant {id, role}, employé créé ou None pour le client)."""
    def _who(role):
        if role == "client":
            return CLIENT, None
        e = make_employe(role)
        return {"id": e["id"], "role": role}, e
    return _who


def change(order_id, new_status, actor, motif=None):
    with cursor() as cur:  # une transaction par appel, comme dans un routeur
        return change_status(cur, order_id, new_status, actor, motif)


def refused(order_id, new_status, actor, code, motif=None):
    with pytest.raises(HTTPException) as e:
        change(order_id, new_status, actor, motif)
    assert e.value.status_code == code, e.value.detail
    return e.value.detail


# ---------------------------------------------------------------- le tableau
def test_table_matches_the_spec():
    by_role = {r: set() for r in SPEC}
    for (frm, to), (roles, _) in TRANSITIONS.items():
        for r in roles:
            by_role[r].add((frm, to))
    assert by_role == SPEC


ALLOWED = [(frm, to, role, mode) for (frm, to), (roles, modes) in TRANSITIONS.items() for role in roles for mode in modes]


@pytest.mark.parametrize("frm,to,role,mode", ALLOWED)
def test_every_allowed_transition_works_and_records_who(frm, to, role, mode, who, make_order, get_order, get_history):
    actor, employe = who(role)
    cmd = make_order(statut=frm, mode=mode, livreur_id=actor["id"] if role == "livreur" else None)
    res = change(cmd["id"], to, actor, motif="client absent")
    assert (res["ancien_statut"], res["statut"], res["id"], res["numero"]) == (frm, to, cmd["id"], cmd["numero"])
    assert get_order(cmd["id"])["statut"] == to
    last = get_history(cmd["id"])[-1]
    assert (last["ancien_statut"], last["nouveau_statut"]) == (frm, to)
    assert last["employe_id"] == (employe["id"] if employe else None)  # le client n'a pas de compte : NULL


FORBIDDEN = [(frm, to, role) for (frm, to), (roles, _) in TRANSITIONS.items() for role in ROLES if role not in roles]


@pytest.mark.parametrize("frm,to,role", FORBIDDEN)
def test_wrong_role_is_refused_and_nothing_changes(frm, to, role, who, make_order, get_order):
    actor, _ = who(role)
    mode = "livraison" if to in ("en_route", "livree", "echec") else "sur_place"
    cmd = make_order(statut=frm, mode=mode)
    assert refused(cmd["id"], to, actor, 403) == "Accès refusé pour votre rôle"
    assert get_order(cmd["id"])["statut"] == frm


def test_wrong_role_learns_nothing_about_the_order(who):
    cuisinier, _ = who("cuisinier")
    refused(99999999, "servie", cuisinier, 403)  # 403 et pas 404 : on ne révèle pas si la commande existe


# ---------------------------------------------------------------- passages impossibles
@pytest.mark.parametrize("frm,to,role", [
    ("recue", "prete", "cuisinier"),            # on ne saute pas « en préparation »
    ("recue", "servie", "serveur"),
    ("en_preparation", "servie", "serveur"),    # pas encore prête
    ("prete", "en_preparation", "cuisinier"),   # pas de retour en arrière
    ("servie", "en_preparation", "cuisinier"),
    ("livree", "en_route", "livreur"),
    ("prete", "livree", "livreur"),             # il faut passer par « en route »
    ("prete", "echec", "livreur"),
    ("en_preparation", "annulee", "caissier"),  # annulation : seulement tant que « reçue »
    ("prete", "annulee", "client"),
    ("servie", "annulee", "caissier"),
    ("annulee", "annulee", "caissier"),
])
def test_impossible_transitions_return_409(frm, to, role, who, make_order, get_order):
    actor, _ = who(role)
    cmd = make_order(statut=frm, mode="livraison", livreur_id=actor["id"] if role == "livreur" else None)
    refused(cmd["id"], to, actor, 409)
    assert get_order(cmd["id"])["statut"] == frm


def test_cancel_message_is_clear(who, make_order):
    caissier, _ = who("caissier")
    cmd = make_order(statut="en_preparation")
    assert "reçues" in refused(cmd["id"], "annulee", caissier, 409)


def test_double_click_second_call_is_refused(who, make_order, get_history):
    cuisinier, _ = who("cuisinier")
    cmd = make_order(statut="recue")
    change(cmd["id"], "en_preparation", cuisinier)
    refused(cmd["id"], "en_preparation", cuisinier, 409)
    assert [h["nouveau_statut"] for h in get_history(cmd["id"])] == ["en_preparation"]  # une seule trace


def test_unknown_statuses_and_missing_order(who, make_order):
    cuisinier, _ = who("cuisinier")
    cmd = make_order()
    for bad in ("recue", "remboursee", "n_importe_quoi"):
        refused(cmd["id"], bad, cuisinier, 422)
    refused(99999999, "en_preparation", cuisinier, 404)


# ---------------------------------------------------------------- mode de la commande
def test_delivery_is_not_served_at_the_table(who, make_order):
    serveur, _ = who("serveur")
    refused(make_order(statut="prete", mode="livraison")["id"], "servie", serveur, 409)


@pytest.mark.parametrize("mode", ["sur_place", "a_emporter"])
def test_on_site_orders_do_not_go_on_the_road(mode, who, make_order):
    livreur, _ = who("livreur")
    refused(make_order(statut="prete", mode=mode, livreur_id=livreur["id"])["id"], "en_route", livreur, 409)


# ---------------------------------------------------------------- livreur
def test_delivery_person_only_touches_own_deliveries(who, make_order, make_employe, get_order):
    mine, _ = who("livreur")
    other = make_employe("livreur")
    cmd = make_order(statut="prete", mode="livraison", livreur_id=other["id"])
    assert refused(cmd["id"], "en_route", mine, 403) == "Cette livraison ne vous est pas assignée"
    unassigned = make_order(statut="prete", mode="livraison")
    refused(unassigned["id"], "en_route", mine, 403)
    assert get_order(cmd["id"])["statut"] == "prete" and get_order(unassigned["id"])["statut"] == "prete"


def test_failed_delivery_needs_a_reason(who, make_order, get_order):
    livreur, _ = who("livreur")
    cmd = make_order(statut="en_route", mode="livraison", livreur_id=livreur["id"])
    for bad in (None, "", "   "):
        refused(cmd["id"], "echec", livreur, 422, motif=bad)
    assert get_order(cmd["id"])["statut"] == "en_route"
    change(cmd["id"], "echec", livreur, motif="  Personne à l'adresse  ")
    o = get_order(cmd["id"])
    assert o["statut"] == "echec" and o["motif_echec"] == "Personne à l'adresse" and o["terminee_at"] is not None


# ---------------------------------------------------------------- annulation et remboursement
def test_cancel_refunds_online_payment(who, make_order, get_order):
    client, _ = who("client")
    paid = make_order(paiement_mode="en_ligne")
    assert paid["paiement_statut"] == "paye"
    res = change(paid["id"], "annulee", client)
    assert (res["statut"], res["paiement_statut"]) == ("annulee", "rembourse")
    assert get_order(paid["id"])["paiement_statut"] == "rembourse"


def test_cancel_cash_order_does_not_touch_payment(who, make_order):
    caissier, _ = who("caissier")
    res = change(make_order(paiement_mode="especes")["id"], "annulee", caissier)
    assert (res["statut"], res["paiement_statut"]) == ("annulee", "en_attente")


# ---------------------------------------------------------------- horodatages (posés par le trigger)
def test_timestamps_follow_the_statuses(who, make_order, get_order):
    cuisinier, _ = who("cuisinier")
    serveur, _ = who("serveur")
    cmd = make_order(statut="recue")
    assert get_order(cmd["id"])["prise_en_charge_at"] is None
    change(cmd["id"], "en_preparation", cuisinier)
    assert get_order(cmd["id"])["prise_en_charge_at"] is not None
    change(cmd["id"], "prete", cuisinier)
    o = get_order(cmd["id"])
    assert o["prete_at"] is not None and o["terminee_at"] is None
    change(cmd["id"], "servie", serveur)
    assert get_order(cmd["id"])["terminee_at"] is not None


def test_full_dine_in_and_delivery_flows(who, make_order, get_history, get_order):
    cuisinier, _ = who("cuisinier")
    serveur, _ = who("serveur")
    livreur, _ = who("livreur")
    sur_place = make_order(mode="sur_place")
    for to, a in (("en_preparation", cuisinier), ("prete", cuisinier), ("servie", serveur)):
        change(sur_place["id"], to, a)
    assert get_order(sur_place["id"])["statut"] == "servie"
    livraison = make_order(mode="livraison", livreur_id=livreur["id"])
    for to, a in (("en_preparation", cuisinier), ("prete", cuisinier), ("en_route", livreur), ("livree", livreur)):
        change(livraison["id"], to, a)
    assert [h["nouveau_statut"] for h in get_history(livraison["id"])] == ["en_preparation", "prete", "en_route", "livree"]


# ---------------------------------------------------------------- deux appels en même temps
def test_two_simultaneous_changes_only_one_wins(who, make_order, get_order, get_history):
    """Le premier appel garde sa transaction ouverte ; le second doit ATTENDRE (verrou FOR UPDATE), puis être refusé."""
    cuisinier, _ = who("cuisinier")
    cmd = make_order(statut="recue")
    first_done, release = threading.Event(), threading.Event()

    def first():
        with cursor() as cur:
            change_status(cur, cmd["id"], "en_preparation", cuisinier)
            first_done.set()
            release.wait(10)  # la transaction (et le verrou) reste ouverte

    def second():
        first_done.wait(10)
        try:
            change(cmd["id"], "en_preparation", cuisinier)
        except HTTPException as e:
            return e.status_code
        return 200

    with ThreadPoolExecutor(2) as pool:
        f1, f2 = pool.submit(first), pool.submit(second)
        time.sleep(0.6)
        assert not f2.done(), "le second appel aurait dû attendre le verrou du premier"
        release.set()
        assert f2.result(10) == 409
        f1.result(10)
    assert [h["nouveau_statut"] for h in get_history(cmd["id"])] == ["en_preparation"]
