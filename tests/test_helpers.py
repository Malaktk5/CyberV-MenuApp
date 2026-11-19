"""Tests that the shared fixtures create valid test data and clean it up."""
import pytest

from app import config
from app.db import cursor

ROLES = ["gerant", "cuisinier", "serveur", "caissier", "livreur"]
STATUTS = ["recue", "en_preparation", "prete", "servie", "en_route", "livree", "echec", "annulee", "remboursee"]
MODES = ["sur_place", "a_emporter", "livraison"]


# ---------------------------------------------------------------- employés et connexion
@pytest.mark.parametrize("role", ROLES)
def test_login_as_gives_a_connected_client_for_every_role(role, login_as):
    c = login_as(role)
    me = c.get("/api/auth/me").json()
    assert me["role"] == role and me["id"] == c.employe["id"]
    assert c.employe["email"].startswith("test-") and c.employe["email"].endswith("@test.local")


def test_make_employe_options(make_employe, anon):
    inactive = make_employe("livreur", actif=False)
    assert anon.post("/api/auth/login", json={"email": inactive["email"], "mot_de_passe": inactive["password"]}).status_code == 401
    custom = make_employe("caissier", password="UnAutreMotDePasse1")
    assert anon.post("/api/auth/login", json={"email": custom["email"], "mot_de_passe": "UnAutreMotDePasse1"}).status_code == 200
    assert make_employe("serveur")["email"] != make_employe("serveur")["email"]  # emails uniques


def test_admin_fixture_is_a_manager(admin):
    assert admin.get("/api/auth/me").json()["role"] == "gerant"
    assert admin.get("/api/admin/stats").status_code == 200


# ---------------------------------------------------------------- plats
def test_make_plat_defaults_and_flags(make_plat, anon):
    p = make_plat(prix=750)
    assert p["nom"].startswith("ZZ_TEST_") and p["prix"] == 750
    menu = {pl["id"]: pl for c in anon.get("/api/menu").json() for pl in c["plats"]}
    assert menu[p["id"]]["disponible"] is True
    off = make_plat(disponible=False)
    assert {pl["id"]: pl for c in anon.get("/api/menu").json() for pl in c["plats"]}[off["id"]]["disponible"] is False
    archived = make_plat(archive=True)
    assert archived["id"] not in {pl["id"] for c in anon.get("/api/menu").json() for pl in c["plats"]}


def test_make_plat_forces_the_cleanup_prefix(make_plat):
    assert make_plat(nom="Salade")["nom"] == "ZZ_TEST_Salade"


# ---------------------------------------------------------------- commandes
def test_make_order_defaults(make_order, get_order, anon):
    cmd = make_order()
    assert (cmd["statut"], cmd["mode"], cmd["paiement_mode"], cmd["paiement_statut"]) == ("recue", "sur_place", "especes", "en_attente")
    assert cmd["numero"].startswith("CMD-") and cmd["total"] == 500 and cmd["note"].startswith("ZZ_TEST_")
    assert get_order(cmd["id"])["numero"] == get_order(cmd["numero"])["numero"] == cmd["numero"]  # par id ou par numéro
    s = anon.get(f"/api/commandes/suivi/{cmd['suivi_token']}").json()  # visible par le client avec son jeton
    assert s["statut"] == "recue" and s["table_numero"] == 1 and s["total"] == 500


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("statut", STATUTS)
def test_make_order_in_every_status_and_mode(statut, mode, make_order, get_order):
    cmd = make_order(statut=statut, mode=mode)
    o = get_order(cmd["id"])
    assert o["statut"] == statut and o["mode"] == mode


def test_make_order_payment_states(make_order, get_order):
    assert get_order(make_order(paiement_mode="en_ligne")["id"])["paiement_statut"] == "paye"
    assert get_order(make_order(paiement_mode="especes")["id"])["paiement_statut"] == "en_attente"
    assert get_order(make_order(paiement_mode="especes", paiement_statut="paye")["id"])["paiement_statut"] == "paye"
    assert get_order(make_order(paiement_mode="en_ligne", paiement_statut="rembourse", statut="annulee")["id"])["paiement_statut"] == "rembourse"


def test_make_order_totals_and_lines(make_order, make_plat, get_order):
    a, b = make_plat(prix=300), make_plat(prix=450)
    cmd = make_order(lignes=[(a, 2), (b["id"], 1)])  # un plat en dict, l'autre par son id
    assert cmd["total"] == 1050 and len(cmd["lignes"]) == 2
    with cursor() as cur:
        cur.execute("SELECT count(*) AS n, sum(total_ligne)::float AS s FROM lignes_commande WHERE commande_id = %s", (cmd["id"],))
        r = cur.fetchone()
    assert (r["n"], r["s"]) == (2, 1050)
    delivery = make_order(mode="livraison", plat=a, quantite=3)
    assert delivery["frais_livraison"] == config.DELIVERY_FEE and delivery["total"] == 900 + config.DELIVERY_FEE
    assert get_order(delivery["id"])["total"] == delivery["total"]


def test_make_order_assignments_and_dates(make_order, make_employe, get_order):
    livreur, serveur = make_employe("livreur"), make_employe("serveur")
    cmd = make_order(mode="livraison", statut="en_route", livreur_id=livreur["id"], serveur_id=serveur["id"], created_at="2026-01-02 12:00:00+00")
    o = get_order(cmd["id"])
    assert (o["livreur_id"], o["serveur_id"]) == (livreur["id"], serveur["id"]) and str(o["created_at"]).startswith("2026-01-02")
    assert get_order(make_order(statut="echec", mode="livraison", motif_echec="porte fermée")["id"])["motif_echec"] == "porte fermée"
    assert get_order(make_order(mode="sur_place", table_numero=3)["id"])["id"]  # une autre table du jeu de départ


def test_make_order_note_always_has_the_cleanup_prefix(make_order):
    assert make_order(note="sans oignons")["note"] == "ZZ_TEST_sans oignons"
    assert make_order(note="ZZ_TEST_deja")["note"] == "ZZ_TEST_deja"


def test_get_history_of_a_made_order(make_order, get_history):
    assert get_history(make_order(statut="recue")["id"]) == []
    h = get_history(make_order(statut="prete")["id"])
    assert [(x["ancien_statut"], x["nouveau_statut"], x["employe_id"]) for x in h] == [("recue", "prete", None)]


# ---------------------------------------------------------------- nettoyage
def test_purge_removes_everything_the_tests_created(admin, make_plat, make_order, make_employe, purge):
    admin.post("/api/admin/categories", json={"nom": "ZZ_TEST_ViaApi"})
    cmd = make_order(paiement_mode="en_ligne", statut="prete")
    make_employe("livreur")
    purge()
    with cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM commandes WHERE id = %s", (cmd["id"],))
        assert cur.fetchone()["n"] == 0
        cur.execute("SELECT count(*) AS n FROM plats WHERE nom LIKE 'ZZ_TEST_%'")
        assert cur.fetchone()["n"] == 0
        cur.execute("SELECT count(*) AS n FROM categories WHERE nom LIKE 'ZZ_TEST_%'")
        assert cur.fetchone()["n"] == 0
        cur.execute("SELECT count(*) AS n FROM employes WHERE email LIKE 'test-%@test.local'")
        assert cur.fetchone()["n"] == 0
        cur.execute("SELECT count(*) AS n FROM historique_statuts WHERE commande_id = %s", (cmd["id"],))
        assert cur.fetchone()["n"] == 0


def test_purge_keeps_real_data(make_plat, purge):
    make_plat()
    purge()
    with cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM plats WHERE nom NOT LIKE 'ZZ_TEST_%'")
        assert cur.fetchone()["n"] >= 7  # le menu de départ de db/init.sql est intact
