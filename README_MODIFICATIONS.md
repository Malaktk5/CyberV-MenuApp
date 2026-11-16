# CyberV-MenuApp — Modifications apportées

Ce document explique tout ce qui a été ajouté ou modifié dans le projet : l'interface du gérant, la page d'accueil avec le menu, la commande client et la réception des commandes. Il décrit aussi les changements faits dans le `Dockerfile`, le `requirements.txt`, le `docker-compose.yml` et la CI.

Le fichier `db/init.sql` n'a pas été modifié. Tout le code s'appuie sur les tables qui existaient déjà.

## Fichiers existants modifiés

**requirements.txt** : on a retiré `pytest`. C'est un outil de test, il n'a pas besoin d'être dans l'image de production. C'est aussi lui qui faisait échouer le build Docker (`No matching distribution found for pytest`) à cause d'un téléchargement coupé. Le reste du fichier est inchangé : `fastapi`, `uvicorn[standard]`, `psycopg2-binary`, `redis` et `httpx`.

**requirements-dev.txt** (nouveau) : il contient `-r requirements.txt` puis `pytest`. On l'utilise pour installer les dépendances de test, en local et dans la CI.

**Dockerfile** : la ligne qui installe les dépendances a été rendue tolérante aux connexions lentes. Le build échouait avec `ReadTimeoutError` parce que le conteneur téléchargeait à 10–40 ko/s. La version utilisée est :

```dockerfile
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=300 --retries 10 -r requirements.txt
```

`--default-timeout=300 --retries 10` fait patienter pip et le fait réessayer au lieu d'abandonner. `--mount=type=cache` garde les paquets déjà téléchargés entre deux builds, donc un build coupé reprend sans tout retélécharger. Pour cela, l'option `--no-cache-dir` a été retirée. Cette option demande BuildKit, qui est actif par défaut avec `docker compose`.

**docker-compose.yml** : deux changements.
- Dans le service `app`, `build:` est passé en `context: .` avec `network: host`. Cela contourne le réseau Docker lent ou bloqué sous Fedora pendant le build. C'est un réglage propre à une machine : si ça gêne l'équipe, on peut le déplacer dans un `docker-compose.override.yml` non commité.
- Ajout du volume `uploads_data:/app/uploads` dans le service `app`, et de `uploads_data:` dans la section `volumes:` du bas. Il garde les photos de plats envoyées par le gérant quand on reconstruit l'image.

**.env** (non versionné) : créé en copiant `.env.example`, puis complété avec `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SECRET_KEY` et `DEMO_DATA`. Sans ce fichier, Docker Compose ne trouvait pas `POSTGRES_USER`, `POSTGRES_PASSWORD` et `POSTGRES_DB`.

**.env.example** : ajout des nouvelles variables, sans aucun secret, pour servir de modèle à l'équipe.

**.gitignore** : ajout de la ligne `uploads/`, pour ne pas commiter les photos envoyées depuis l'interface.

**.github/workflows/ci.yml** : `pip install -r requirements.txt` est devenu `pip install -r requirements-dev.txt`. Comme `pytest` n'est plus dans `requirements.txt`, sans ce changement la CI aurait échoué.

**app/main.py** : réécrit. La route `/health` est identique, donc les tests d'origine passent toujours. Le fichier branche en plus les nouveaux routeurs, sert les dossiers `/uploads` et le site, et crée le compte gérant au démarrage.

## Nouveaux fichiers

Dossier `app/` :
- `config.py` : réglages (clé secrète, frais de livraison, fuseau horaire, dossier des photos).
- `db.py` : connexion à PostgreSQL et transactions.
- `security.py` : hachage des mots de passe, sessions signées et contrôle des rôles.
- `seed.py` : création du compte gérant et données de démonstration.
- `menu_seed.json` : les 26 plats du restaurant avec leurs photos.
- `routers/auth.py` : connexion, déconnexion, utilisateur courant.
- `routers/public.py` : menu public.
- `routers/admin.py` : catégories, plats, employés, statistiques et commandes du gérant.
- `routers/commandes.py` : commande client, options de commande et suivi.

Dossier `frontend/` :
- `index.html` : accueil, menu, panier, contact et carte.
- `suivi.html` : suivi de commande pour le client.
- `admin/login.html` et `admin/index.html` : connexion et espace gérant.
- `assets/css/` : `base.css`, `public.css`, `admin.css`.
- `assets/js/shared/`, `assets/js/public/`, `assets/js/admin/` : le JavaScript, un fichier par vue.
- `assets/img/` : logo, photos des plats (optimisées) et photos de la section « Notre histoire ».

Dossier `tests/` : `__init__.py`, `test_admin.py` et `test_commandes.py`.

Aucune dépendance Python n'a été ajoutée : le hachage des mots de passe, les sessions et l'envoi de photos utilisent seulement la bibliothèque standard.

## Variables d'environnement

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` : la base de données (déjà existantes).
- `ADMIN_EMAIL` et `ADMIN_PASSWORD` : le compte gérant, créé au premier démarrage s'il n'existe pas. Sans elles, aucun compte n'est créé.
- `SECRET_KEY` : sert à signer les cookies de session. Mets une longue chaîne aléatoire.
- `DEMO_DATA` : à `1`, charge le menu avec photos et trois semaines de fausses commandes. À mettre à `0` en production.
- `DELIVERY_FEE` (optionnelle, 200 par défaut) : frais de livraison en DA.
- `ORDER_RATE_LIMIT` (optionnelle, 10 par défaut) : nombre maximum de commandes par minute et par adresse IP.
- `TZ_OFFSET_HOURS` (optionnelle, 1 par défaut) : décalage horaire du restaurant.

Le mot de passe du gérant n'est créé qu'une seule fois. Changer `ADMIN_PASSWORD` plus tard ne modifie pas un compte existant : il faut passer par la page Employés, bouton « Nouveau mot de passe ».

## Fonctionnalités ajoutées

**Page d'accueil.** Le menu est chargé depuis la base, avec un filtre par catégorie et une recherche. Les plats épuisés sont grisés. On y trouve aussi les photos, l'histoire du restaurant, une galerie, la carte Google Maps et un bouton d'itinéraire. Le style reprend celui de `Menu.html` : police Quicksand et or `#e4b95b`.

**Commande client, sans compte.** Le client ajoute des plats au panier (mémorisé dans le navigateur) et peut écrire une remarque par plat. Il choisit ensuite le mode : sur place (avec le numéro de table), à emporter ou livraison (nom, téléphone, adresse et frais). Il peut ajouter une note pour la cuisine, puis payer en espèces ou par carte. Le paiement par carte est simulé : aucune donnée de carte n'est envoyée ni enregistrée. Une page de suivi, `/suivi.html?t=...`, montre l'avancement de la commande.

**Espace gérant** (`/admin/`) :
- **Tableau de bord** : recette, nombre de clients, panier moyen, plats vendus, temps de préparation moyen, annulations, plats les plus vendus et heures de pointe, par jour, semaine, mois ou année.
- **Commandes** : la liste se met à jour toutes les 5 secondes. Un badge, une notification et un son signalent les nouvelles commandes. Il y a des filtres, une recherche, et le gérant peut annuler une commande tant qu'elle est « reçue ».
- **Plats** : ajout, modification, suppression, archivage et restauration, avec photo. La case « Disponible » grise le plat quand on la décoche.
- **Catégories** : ajout, modification et suppression.
- **Employés** : création de comptes par rôle, activation ou désactivation, changement de mot de passe.

**Sécurité.** Les prix sont toujours relus dans la base : le navigateur ne peut pas imposer un total. Un plat épuisé ou archivé est refusé à la commande. Le nombre de commandes est limité. L'espace admin est réservé au rôle `gerant` (le cuisinier peut seulement changer la disponibilité d'un plat). Les mots de passe sont hachés avec scrypt et le cookie de session est `HttpOnly`.

## Routes de l'API ajoutées

Accès public :
- `GET /api/menu`
- `GET /api/options-commande`
- `POST /api/commandes`
- `GET /api/commandes/suivi/{token}`
- `POST /api/auth/login`, `POST /api/auth/logout`

Accès connecté :
- `GET /api/auth/me`
- `PATCH /api/staff/plats/{id}/disponibilite` (gérant et cuisinier)

Accès gérant :
- `/api/admin/categories`, `/api/admin/plats` (avec `archiver` et `restaurer`), `/api/admin/upload`
- `/api/admin/employes`
- `GET /api/admin/stats?period=day|week|month|year`
- `GET /api/admin/commandes`, `GET /api/admin/commandes/resume`, `POST /api/admin/commandes/{id}/annuler`

La documentation interactive est disponible sur `http://localhost:8000/docs`.

## Base de données

Le schéma est inchangé. Les tables utilisées sont `employes`, `categories`, `plats`, `commandes`, `lignes_commande`, `tables_restaurant` et `historique_statuts` (remplie par le trigger lors d'une annulation). Les règles SQL existantes sont respectées : une annulation n'est possible que depuis le statut `recue`, et un plat indisponible est refusé. La table `options_plat` n'est pas encore utilisée.

Avec `DEMO_DATA=1`, le programme ajoute les plats de `menu_seed.json` sans toucher à ceux qui existent déjà (sauf leur photo si elle est vide). Il crée aussi quelques employés de démonstration avec des mots de passe aléatoires, à réinitialiser depuis l'admin, ainsi que des commandes fictives pour remplir les statistiques.

## Lancer le projet

```bash
cp .env.example .env          # puis remplir les valeurs
docker compose down -v        # repart d'une base propre (recharge init.sql)
docker compose up --build -d
docker compose logs app --tail=20     # doit afficher « [seed] Compte gérant créé »
```

- Accueil : http://localhost:8000/
- Connexion du personnel : http://localhost:8000/admin/login.html (email et mot de passe = `ADMIN_EMAIL` et `ADMIN_PASSWORD`)

Pour lancer les tests, la base doit tourner et `db/init.sql` doit être chargé :

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. DATABASE_URL=postgresql://yummy_user:yummy_password@localhost:5433/yummy_db python -m pytest -q
```

Les 5 tests d'origine et les 22 nouveaux passent, soit 27 au total.


