"""Données de départ : compte gérant (depuis .env) et, en démo, employés + commandes pour les statistiques."""
import json, os, random, secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app import config
from app.db import cursor
from app.security import hash_password


def create_admin():
    email, pw = os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")
    if not email or not pw:
        print("[seed] ADMIN_EMAIL / ADMIN_PASSWORD absents du .env : aucun compte gérant créé.")
        return
    with cursor() as cur:
        cur.execute("SELECT 1 FROM employes WHERE lower(email) = lower(%s)", (email,))
        if not cur.fetchone():
            cur.execute("INSERT INTO employes (nom, prenom, email, mot_de_passe_hash, role) VALUES ('Admin', 'Yummy', %s, %s, 'gerant')",
                        (email.lower(), hash_password(pw)))
            print(f"[seed] Compte gérant créé : {email}")


ALIAS = {"café": "café expresso"}  # plats de init.sql dont le nom diffère un peu du menu du restaurant


def seed_menu():
    """Ajoute les plats du menu (app/menu_seed.json) avec leurs photos ; idempotent, ne modifie jamais un plat existant sauf sa photo vide."""
    items = json.loads((Path(__file__).parent / "menu_seed.json").read_text(encoding="utf-8"))
    by_name = {i["nom"].lower(): i for i in items}
    with cursor() as cur:
        cur.execute("SELECT id, nom, photo_url FROM plats")
        existing = {r["nom"].lower(): r for r in cur.fetchall()}
        for key, row in existing.items():
            item = by_name.get(ALIAS.get(key, key))
            if item and not row["photo_url"]:
                cur.execute("UPDATE plats SET photo_url = %s WHERE id = %s", (item["photo_url"], row["id"]))
        cur.execute("SELECT id, nom FROM categories")
        cats = {r["nom"]: r["id"] for r in cur.fetchall()}
        covered = set(existing) | {ALIAS[k] for k in existing if k in ALIAS}
        for i in items:
            if i["nom"].lower() in covered or i["categorie"] not in cats:
                continue
            cur.execute("INSERT INTO plats (categorie_id, nom, description, prix, photo_url) VALUES (%s, %s, %s, %s, %s)",
                        (cats[i["categorie"]], i["nom"], i["description"], i["prix"], i["photo_url"]))


def seed_demo():
    rnd = random.Random(7)
    with cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM commandes")
        if cur.fetchone()["n"]:
            return
        for nom, prenom, role in [("Benali", "Karim", "cuisinier"), ("Hadj", "Sarah", "serveur"), ("Messaoud", "Lina", "caissier"), ("Saidi", "Yacine", "livreur")]:
            cur.execute("""INSERT INTO employes (nom, prenom, email, mot_de_passe_hash, role) VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT (email) DO NOTHING""", (nom, prenom, f"{prenom.lower()}@yummy.dz", hash_password(secrets.token_urlsafe(12)), role))
        cur.execute("SELECT id, nom, prix::float AS prix FROM plats WHERE disponible AND NOT archive")
        plats = cur.fetchall()
        cur.execute("SELECT id FROM tables_restaurant")
        tables = [r["id"] for r in cur.fetchall()]
        now = datetime.now(timezone.utc)
        for d in range(21, -1, -1):
            for _ in range(rnd.randint(8, 22)):
                hour = rnd.choice([11, 12, 12, 12, 13, 13, 14, 19, 19, 20, 20, 21])
                t = (now - timedelta(days=d)).replace(hour=(hour - config.TZ_HOURS) % 24, minute=rnd.randint(0, 59), second=0, microsecond=0)
                if t > now:
                    continue
                mode = rnd.choice(["sur_place"] * 3 + ["a_emporter", "livraison"])
                recent = now - t < timedelta(hours=3)
                final = rnd.choices(["servie" if mode != "livraison" else "livree", "annulee"], [92, 8])[0]
                if recent:
                    final = rnd.choice(["recue", "en_preparation", "prete"])
                cur.execute("""INSERT INTO commandes (mode, table_id, client_nom, client_telephone, adresse_livraison, paiement_mode, created_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                            (mode, rnd.choice(tables) if mode == "sur_place" else None, "Client", "0550000000" if mode == "livraison" else None,
                             "Adresse de démonstration" if mode == "livraison" else None, rnd.choice(["especes", "en_ligne"]), t))
                oid, sous = cur.fetchone()["id"], 0.0
                for p in rnd.sample(plats, rnd.randint(1, min(3, len(plats)))):
                    q = rnd.randint(1, 3); sous += p["prix"] * q
                    cur.execute("INSERT INTO lignes_commande (commande_id, plat_id, nom_plat, prix_unitaire, quantite, total_ligne) VALUES (%s,%s,%s,%s,%s,%s)",
                                (oid, p["id"], p["nom"], p["prix"], q, p["prix"] * q))
                frais = 200 if mode == "livraison" else 0
                paye = "paye" if final in ("servie", "livree") else "en_attente"
                cur.execute("UPDATE commandes SET sous_total=%s, frais_livraison=%s, total=%s, statut=%s, paiement_statut=%s WHERE id=%s",
                            (sous, frais, sous + frais, final, paye, oid))
                pec = t + timedelta(minutes=rnd.randint(2, 5)); prete = pec + timedelta(minutes=rnd.randint(8, 30))
                if final == "annulee":
                    times = (None, None, t + timedelta(minutes=rnd.randint(1, 3)))
                elif final == "recue":
                    times = (None, None, None)
                elif final == "en_preparation":
                    times = (pec, None, None)
                elif final == "prete":
                    times = (pec, prete, None)
                else:
                    times = (pec, prete, prete + timedelta(minutes=rnd.randint(3, 10)))
                cur.execute("UPDATE commandes SET prise_en_charge_at=%s, prete_at=%s, terminee_at=%s WHERE id=%s", (*times, oid))
        print("[seed] Données de démonstration créées.")


def bootstrap():
    create_admin()
    if os.getenv("DEMO_DATA") == "1":
        seed_menu()
        seed_demo()
