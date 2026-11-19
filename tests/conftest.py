"""Shared test fixtures for creating users, menu items, and orders.

Tests can request fixtures such as `login_as`, `make_employe`, `make_plat`,
`make_order`, `get_order`, and `get_history`. Test data is automatically
removed after each test that touches the database.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app import config
from app.db import cursor
from app.main import app
from app.routers import commandes as commandes_router
from app.security import hash_password

PWD = "Secret123!"
TEST = "ZZ_TEST_"            # préfixe des plats, catégories et notes de commande créés par les tests
EMAIL_PREFIX = "test-"        # les employés de test : test-xxxxxxxx@test.local
EMAIL_DOMAIN = "@test.local"

_db = {"used": False}         # vrai dès qu'un test a créé quelque chose en base : déclenche le nettoyage


def _touch_db():
    _db["used"] = True


# ---------------------------------------------------------------- employés et connexion
def create_employe(role="serveur", actif=True, password=PWD):
    _touch_db()
    email = f"{EMAIL_PREFIX}{uuid.uuid4().hex[:8]}{EMAIL_DOMAIN}"
    with cursor() as cur:
        cur.execute("""INSERT INTO employes (nom, prenom, email, mot_de_passe_hash, role, actif)
                       VALUES ('Test', %s, %s, %s, %s, %s) RETURNING id""", (role, email, hash_password(password), role, actif))
        return {"id": cur.fetchone()["id"], "email": email, "role": role, "password": password}


def login(email, password=PWD):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "mot_de_passe": password})
    assert r.status_code == 200, f"connexion refusée : {r.status_code} {r.text}"
    return c


def logged_client(role="gerant"):
    e = create_employe(role)
    c = login(e["email"], e["password"])
    c.employe = e
    return c


# ---------------------------------------------------------------- plats
def create_plat(prix=500, nom=None, disponible=True, archive=False, temps_preparation=10, categorie_id=None):
    _touch_db()
    with cursor() as cur:
        if categorie_id is None:
            cur.execute("INSERT INTO categories (nom, ordre) VALUES (%s, 99) RETURNING id", (f"{TEST}Cat_{uuid.uuid4().hex[:8]}",))
            categorie_id = cur.fetchone()["id"]
        nom = nom or f"{TEST}Plat_{uuid.uuid4().hex[:8]}"
        if not nom.startswith(TEST):
            nom = TEST + nom
        cur.execute("""INSERT INTO plats (categorie_id, nom, prix, temps_preparation, disponible, archive)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, nom, prix::float AS prix, categorie_id, temps_preparation""",
                    (categorie_id, nom, prix, temps_preparation, disponible, archive))
        return cur.fetchone()


# ---------------------------------------------------------------- commandes
def create_order(statut="recue", mode="sur_place", paiement_mode="especes", paiement_statut=None, plat=None, quantite=1,
                 lignes=None, table_numero=1, livreur_id=None, serveur_id=None, note=None, client_nom=None,
                 client_telephone=None, adresse_livraison=None, motif_echec=None, created_at=None):
    """Crée une commande directement en base, déjà au statut voulu (sans passer par l'API, donc sans règle de transition).

    plat / quantite   une seule ligne ; sans `plat`, un plat de test neuf est créé.
    lignes            [(plat, quantite), ...] pour plusieurs plats (remplace plat/quantite). `plat` peut être un dict ou un id.
    paiement_statut   par défaut « paye » pour le paiement en ligne, « en_attente » pour les espèces.
    Les statuts autres que « recue » sont posés après coup : l'historique contient alors une ligne recue -> statut sans employé.
    La note commence toujours par ZZ_TEST_ (ajouté si besoin) : c'est ce qui permet le nettoyage.
    """
    _touch_db()
    if lignes is None:
        lignes = [(plat or create_plat(), quantite)]
    note = note or ""
    if not note.startswith(TEST):
        note = TEST + (note or f"commande_{uuid.uuid4().hex[:6]}")
    if mode != "sur_place":
        client_nom = client_nom or "Client Test"
        client_telephone = client_telephone or "0550123456"
    if mode == "livraison":
        adresse_livraison = adresse_livraison or "12 rue des Tests"
    with cursor() as cur:
        table_id = None
        if mode == "sur_place":
            cur.execute("SELECT id FROM tables_restaurant WHERE numero = %s", (table_numero,))
            table_id = cur.fetchone()["id"]
        cur.execute("""INSERT INTO commandes (mode, table_id, serveur_id, livreur_id, client_nom, client_telephone, adresse_livraison,
                                              note, paiement_mode, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, now())) RETURNING id, numero, suivi_token""",
                    (mode, table_id, serveur_id, livreur_id, client_nom, client_telephone, adresse_livraison, note, paiement_mode, created_at))
        cmd, sous, resolved = cur.fetchone(), 0.0, []
        for p, q in lignes:
            pid = p["id"] if isinstance(p, dict) else p
            cur.execute("SELECT id, nom, prix::float AS prix FROM plats WHERE id = %s", (pid,))
            row = cur.fetchone()
            sous += row["prix"] * q
            cur.execute("""INSERT INTO lignes_commande (commande_id, plat_id, nom_plat, prix_unitaire, quantite, total_ligne)
                           VALUES (%s, %s, %s, %s, %s, %s)""", (cmd["id"], row["id"], row["nom"], row["prix"], q, row["prix"] * q))
            resolved.append((row, q))
        frais = float(config.DELIVERY_FEE) if mode == "livraison" else 0.0
        if paiement_statut is None:
            paiement_statut = "paye" if paiement_mode == "en_ligne" else "en_attente"
        # les lignes sont déjà posées : on peut maintenant quitter « recue »
        cur.execute("""UPDATE commandes SET sous_total = %s, frais_livraison = %s, total = %s, paiement_statut = %s,
                                            statut = %s, motif_echec = %s WHERE id = %s""",
                    (sous, frais, sous + frais, paiement_statut, statut, motif_echec, cmd["id"]))
    return {"id": cmd["id"], "numero": cmd["numero"], "suivi_token": str(cmd["suivi_token"]), "mode": mode, "statut": statut,
            "paiement_mode": paiement_mode, "paiement_statut": paiement_statut, "sous_total": sous, "frais_livraison": frais,
            "total": sous + frais, "note": note, "lignes": resolved}


def _where(ref):
    return ("id", ref) if isinstance(ref, int) else ("numero", ref)


def fetch_order(ref):
    col, val = _where(ref)
    with cursor() as cur:
        cur.execute(f"""SELECT id, numero, mode::text AS mode, statut::text AS statut, paiement_mode::text AS paiement_mode,
                               paiement_statut::text AS paiement_statut, motif_echec, livreur_id, serveur_id, total::float AS total,
                               created_at, prise_en_charge_at, prete_at, terminee_at
                        FROM commandes WHERE {col} = %s""", (val,))
        return cur.fetchone()


def fetch_history(ref):
    col, val = _where(ref)
    with cursor() as cur:
        cur.execute(f"""SELECT h.ancien_statut::text AS ancien_statut, h.nouveau_statut::text AS nouveau_statut, h.employe_id
                        FROM historique_statuts h JOIN commandes c ON c.id = h.commande_id WHERE c.{col} = %s ORDER BY h.id""", (val,))
        return cur.fetchall()


# ---------------------------------------------------------------- nettoyage
def purge_test_data():
    """Supprime tout ce qui porte la marque des tests, dans l'ordre imposé par les clés étrangères."""
    like_plat, like_mail = TEST + "%", f"{EMAIL_PREFIX}%{EMAIL_DOMAIN}"
    with cursor() as cur:
        cur.execute("""DELETE FROM commandes
                       WHERE note LIKE %(plat)s
                          OR serveur_id IN (SELECT id FROM employes WHERE email LIKE %(mail)s)
                          OR livreur_id IN (SELECT id FROM employes WHERE email LIKE %(mail)s)
                          OR id IN (SELECT l.commande_id FROM lignes_commande l JOIN plats p ON p.id = l.plat_id WHERE p.nom LIKE %(plat)s)""",
                    {"plat": like_plat, "mail": like_mail})            # lignes et historique partent en cascade
        cur.execute("DELETE FROM options_plat WHERE plat_id IN (SELECT id FROM plats WHERE nom LIKE %s)", (like_plat,))
        cur.execute("DELETE FROM plats WHERE nom LIKE %s", (like_plat,))
        cur.execute("DELETE FROM categories WHERE nom LIKE %s", (like_plat,))
        cur.execute("DELETE FROM employes WHERE email LIKE %s", (like_mail,))


@pytest.fixture(autouse=True)
def _clean_after_each_test():
    commandes_router._hits.clear()          # limite de commandes par IP : repart de zéro à chaque test
    yield
    if _db["used"]:
        purge_test_data()
        _db["used"] = False


# ---------------------------------------------------------------- fixtures
@pytest.fixture
def anon():
    return TestClient(app)


@pytest.fixture
def admin():
    return logged_client("gerant")


@pytest.fixture
def login_as():
    return logged_client


@pytest.fixture
def make_employe():
    return create_employe


@pytest.fixture
def make_plat():
    return create_plat


@pytest.fixture
def make_order():
    return create_order


@pytest.fixture
def get_order():
    return fetch_order


@pytest.fixture
def get_history():
    return fetch_history


@pytest.fixture
def purge():
    return purge_test_data
