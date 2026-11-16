# CyberV-MenuApp — Journal des modifications

Ce document liste **tout ce qui a été ajouté ou modifié** dans le dépôt pour l'interface Gérant/Admin,
la page d'accueil avec menu, la commande client et la réception des commandes, y compris les changements
de `Dockerfile`, `requirements.txt`, `docker-compose.yml` et de la CI.

> Le schéma `db/init.sql` n'a **pas été modifié**. Tout le code s'appuie sur les tables existantes.

---

## 1. Fichiers existants modifiés

| Fichier | Modification | Pourquoi |
|---|---|---|
| `requirements.txt` | Retrait de `pytest` (le reste est inchangé : `fastapi`, `uvicorn[standard]`, `psycopg2-binary`, `redis`, `httpx`). | `pytest` est un outil de test : il n'a rien à faire dans l'image de production. C'est aussi lui qui a fait échouer le premier build (`No matching distribution found for pytest`) à cause d'un téléchargement coupé. |
| `requirements-dev.txt` (**nouveau**) | Contient `-r requirements.txt` puis `pytest`. | Installer les dépendances de test en local et dans la CI : `pip install -r requirements-dev.txt`. |
| `Dockerfile` | La ligne `RUN pip install ...` est rendue tolérante aux réseaux lents (voir ci-dessous). | Le build échouait avec `ReadTimeoutError` : le conteneur téléchargeait à 10–40 ko/s. |
| `docker-compose.yml` | 1) `build:` passe en `context: .` + `network: host`. 2) Ajout du volume `uploads_data:/app/uploads` au service `app` et de `uploads_data:` dans `volumes:`. | 1) Contourne le réseau Docker lent ou bloqué sous Fedora pendant le build. 2) Conserve les photos de plats envoyées par le gérant lors des reconstructions. |
| `.env` (non versionné) | Créé en copiant `.env.example`, puis complété avec `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SECRET_KEY`, `DEMO_DATA`. | Sans `.env`, Docker Compose ne trouvait pas `POSTGRES_USER`, `POSTGRES_PASSWORD` et `POSTGRES_DB` (erreur `.env not found`). |
| `.env.example` | Ajout des nouvelles variables (voir §3), sans aucun secret. | Modèle partagé avec l'équipe. |
| `.gitignore` | Ajout de la ligne `uploads/`. | Les photos envoyées via l'interface ne doivent pas être commitées. |
| `.github/workflows/ci.yml` | `pip install -r requirements.txt` devient `pip install -r requirements-dev.txt`. | `pytest` n'est plus dans `requirements.txt` : sans ce changement la CI échouerait (`No module named pytest`). |
| `app/main.py` | Réécrit : `/health` est **identique** (les tests existants passent toujours), plus l'enregistrement des routeurs, le service des fichiers statiques `/uploads` et `/`, et la création du compte gérant au démarrage. | Brancher l'interface et la nouvelle API sur l'application existante. |

### `Dockerfile` — version recommandée

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=300 --retries 10 -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- `--default-timeout=300 --retries 10` : pip patiente et réessaie au lieu d'abandonner sur une connexion lente.
- `--mount=type=cache` : les paquets déjà téléchargés sont gardés entre deux builds (nécessite BuildKit, actif par défaut avec `docker compose`).
- Option : remplacer `uvicorn[standard]` par `uvicorn` dans `requirements.txt` évite de télécharger `uvloop`, `httptools`, `watchfiles` et `websockets` (plus léger).

### `docker-compose.yml` — passages modifiés

```yaml
services:
  app:
    build:
      context: .
      network: host            # contournement réseau pour le build (voir remarque)
    volumes:
      - uploads_data:/app/uploads   # photos des plats
    # ... (reste inchangé)

volumes:
  postgres_data:
  uploads_data:
```

> **Remarque** : `network: host` est un contournement propre à une machine dont le réseau Docker est lent. Si cela gêne le reste de l'équipe,
> déplace-le dans un `docker-compose.override.yml` non commité.

---

## 2. Nouveaux fichiers

```
app/
  config.py              # réglages (clé secrète, frais de livraison, fuseau, dossier d'upload)
  db.py                  # connexion PostgreSQL + transactions
  security.py            # mots de passe (scrypt), sessions signées, contrôle des rôles
  seed.py                # compte gérant (depuis .env) + données de démonstration
  menu_seed.json         # les 26 plats du restaurant avec photos
  routers/
    auth.py              # connexion, déconnexion, utilisateur courant
    public.py            # menu public
    admin.py             # catégories, plats, employés, statistiques, commandes du gérant
    commandes.py         # commande client, options, suivi
frontend/
  index.html             # accueil + menu + panier + contact et carte
  suivi.html             # suivi de commande par le client
  admin/                 # login.html + index.html (espace gérant)
  assets/css/            # base.css, public.css, admin.css
  assets/js/shared/      # api.js, utils.js
  assets/js/public/      # home.js, cart.js, checkout.js
  assets/js/admin/       # app.js, dashboard.js, commandes.js, plats.js, categories.js, employes.js
  assets/img/            # logo, photos des plats (optimisées), photos « à propos »
tests/
  __init__.py
  test_admin.py          # authentification, CRUD, disponibilité, statistiques, employés, upload
  test_commandes.py      # parcours de commande et réception côté gérant
requirements-dev.txt
README_MODIFICATIONS.md
```

Aucune nouvelle dépendance Python n'a été ajoutée (hachage de mots de passe, sessions et upload utilisent uniquement la bibliothèque standard).

---

## 3. Variables d'environnement

| Variable | Rôle | Défaut |
|---|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Base de données (déjà existantes) | — |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Compte gérant créé au premier démarrage s'il n'existe pas. **Sans elles, aucun compte n'est créé.** | — |
| `SECRET_KEY` | Signature des cookies de session | valeur de développement |
| `DEMO_DATA` | `1` : charge le menu avec photos et 3 semaines de fausses commandes | désactivé |
| `DELIVERY_FEE` | Frais de livraison (DA) | `200` |
| `ORDER_RATE_LIMIT` | Commandes max. par minute et par IP | `10` |
| `TZ_OFFSET_HOURS` | Décalage horaire du restaurant | `1` |

> Le mot de passe d'un compte n'est créé qu'une fois : changer `ADMIN_PASSWORD` plus tard ne modifie pas un compte existant
> (utiliser la page **Employés** > « Nouveau mot de passe »).

---

## 4. Fonctionnalités ajoutées

**Page d'accueil (client)** : menu par catégories chargé depuis la base, filtre par catégorie, recherche, plats épuisés grisés,
photos, histoire, galerie, carte Google Maps et itinéraire. Style repris de `Menu.html` (Quicksand, or `#e4b95b`).

**Commande client (sans compte)** : panier mémorisé dans le navigateur, remarque par plat, puis choix **Sur place** (numéro de table),
**À emporter** ou **Livraison** (nom, téléphone, adresse, frais), note pour la cuisine, paiement **Espèces** ou **Carte** (simulé :
aucune donnée de carte n'est envoyée ni stockée). Une page de **suivi** (`/suivi.html?t=...`) affiche l'avancement.

**Espace gérant** (`/admin/`) :
- **Tableau de bord** : recette, clients, panier moyen, plats vendus, temps de préparation, annulations, top plats, heures de pointe, par jour/semaine/mois/année.
- **Commandes** : réception en temps quasi réel (actualisation toutes les 5 s), badge, notification et son, filtres, recherche, annulation d'une commande « reçue ».
- **Plats** : ajout, modification, suppression, archivage/restauration, photo, **case « Disponible »** qui grise le plat.
- **Catégories** : CRUD complet.
- **Employés** : création de comptes par rôle, activation, changement de mot de passe.

**Règles de sécurité** : les prix sont toujours relus en base ; un plat épuisé ou archivé est refusé ; limitation du nombre de commandes ; accès
admin réservé au rôle `gerant` ; l'activation de la disponibilité est aussi ouverte au `cuisinier` ; mots de passe hachés (scrypt) ; cookie `HttpOnly`.

---

## 5. API ajoutée

| Méthode | Route | Accès |
|---|---|---|
| POST | `/api/auth/login`, `/api/auth/logout` · GET `/api/auth/me` | public / connecté |
| GET | `/api/menu` | public |
| GET | `/api/options-commande` · POST `/api/commandes` · GET `/api/commandes/suivi/{token}` | public |
| PATCH | `/api/staff/plats/{id}/disponibilite` | gérant, cuisinier |
| GET/POST/PUT/DELETE | `/api/admin/categories`, `/api/admin/plats` (+ `archiver`, `restaurer`), `/api/admin/upload` | gérant |
| GET/POST/PATCH | `/api/admin/employes` | gérant |
| GET | `/api/admin/stats?period=day\|week\|month\|year` | gérant |
| GET | `/api/admin/commandes`, `/api/admin/commandes/resume` · POST `/api/admin/commandes/{id}/annuler` | gérant |

---

## 6. Base de données

`db/init.sql` est inchangé. Tables utilisées : `employes`, `categories`, `plats`, `commandes`, `lignes_commande`, `tables_restaurant`, `historique_statuts`
(via le trigger lors d'une annulation). Les triggers existants sont respectés (annulation seulement depuis `recue`, plat indisponible refusé).
Pas encore utilisées : `options_plat`.

Avec `DEMO_DATA=1`, `app/seed.py` ajoute les plats de `app/menu_seed.json` (sans toucher aux plats déjà présents, hormis leur photo si elle est vide),
quelques employés de démonstration (mots de passe aléatoires, à réinitialiser depuis l'admin) et des commandes fictives.

---

## 7. Lancer le projet

```bash
cp .env.example .env          # puis remplir les valeurs
docker compose down -v        # repart d'une base propre (recharge init.sql)
docker compose up --build -d
docker compose logs app --tail=20     # doit afficher « [seed] Compte gérant créé »
```

- Accueil : <http://localhost:8000/>
- Connexion du personnel : <http://localhost:8000/admin/login.html> (email et mot de passe = `ADMIN_EMAIL` / `ADMIN_PASSWORD`)
- Documentation de l'API : <http://localhost:8000/docs>

**Tests** (la base doit tourner et `db/init.sql` être chargé) :

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. DATABASE_URL=postgresql://yummy_user:yummy_password@localhost:5433/yummy_db python -m pytest -q
```

Les 5 tests d'origine et les 22 nouveaux passent (27 au total).

---

## 8. Problèmes rencontrés et solutions

| Symptôme | Cause | Solution |
|---|---|---|
| `.env not found` + variables `POSTGRES_*` vides | `.env` non versionné, donc absent après un `git clone` | `cp .env.example .env` |
| `No matching distribution found for pytest` pendant le build | Téléchargement coupé dans le conteneur | `pytest` déplacé dans `requirements-dev.txt` |
| `ReadTimeoutError` sur `files.pythonhosted.org` | Réseau Docker lent (10–40 ko/s) | Timeouts/retries et cache pip dans le `Dockerfile`, `network: host` pour le build |
| `{"detail":"Not Found"}` sur `/admin/login.html` | Dossier `frontend/admin` absent du disque (extraction incomplète) | Réextraire les fichiers, puis `docker compose up --build -d` |
| `404` sur `/uploads/...jpg` | Photo envoyée avant l'ajout du volume `uploads_data` | Vérifier le volume, puis renvoyer la photo |

---

## 9. Reste à faire

- Écran **cuisine** (statuts reçue, en préparation, prête) et écran **serveur** avec son, puis caissier et livreur.
- **Options et suppléments** des plats (table `options_plat`).
- Avis clients, promotions et stock (pas de table dans le schéma actuel).
- Temps réel via **Redis** (aujourd'hui, actualisation toutes les 5 s) et QR code par table (colonne `qr_token`).
- Production : cookie `Secure` derrière HTTPS, `DEMO_DATA=0`, vraie `SECRET_KEY`.
