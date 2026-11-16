# CyberV-MenuApp

**Thème 15 :** Commandes de restaurant

**Équipe :** CyberV (Zemmour Sihame, Moad Kenza, Saadi Ameterrahmane, Touafek Malak, Redjradj Nicette)

---

### Objectif
Numériser la prise de commande d'un restaurant : le client commande depuis son téléphone (sur place via un QR code de table, à emporter ou en livraison), la cuisine reçoit les commandes en temps réel et le gérant suit l'activité.

---

### Fonctionnalités attendues

* **Menu :** catégories, plats (prix, photo, description, options et suppléments, disponibilité), menus du jour.
* **Commande client sur mobile sans installation :** panier, mode de service (sur place avec numéro de table, à emporter, livraison), commentaire.
* **Paiement :** espèces à la caisse ou paiement en ligne simulé (passerelle de test) ; l'application ne stocke jamais de numéro de carte.
* **Cuisine :** écran de préparation en temps réel avec statuts (reçue, en préparation, prête, servie ou livrée) et temps d'attente estimé.
* **Salle et caisse :** suivi des tables, encaissement, annulation ou modification contrôlée avant le début de la préparation.
* **Livraison (option) :** affectation à un livreur et suivi du statut.
* **Stock simple (option) :** décrémentation et mise en rupture automatique d'un plat.
* **Gestion :** promotions, historique des commandes, statistiques (plats les plus vendus, chiffre d'affaires, heures de pointe) ; avis des clients (option).

---

### Acteurs et droits
Client, serveur, cuisinier, caissier, livreur, gérant (menu, statistiques), administrateur.

---

### Données principales
Plat, Catégorie, Option, Menu, Table, Commande, Ligne de commande, Paiement, Statut, Livraison, Stock, Promotion, Avis.

---

### Spécificités DevOps
Le thème se prête à un test de charge qui simule un coup de feu, et à l'observabilité (temps de réponse, nombre de commandes en cours) ; un déploiement avec redémarrage progressif évite d'interrompre le service pendant les repas.

---

## Technologies

| Rôle | Technologie |
|---|---|
| Backend | Python 3, FastAPI (uvicorn) |
| Base de données | PostgreSQL 15 |
| Cache et temps réel | Redis 7 (Pub/Sub) et WebSocket |
| Reverse proxy | Nginx 1.27 |
| Tests | Pytest |
| Conteneurs | Docker et Docker Compose |
| Intégration continue | GitHub Actions |

---

## 1. Prérequis

* **Git**
* **Docker** avec **Docker Compose** (commande `docker compose`)
* Pour lancer les tests en dehors de Docker : **Python 3.11 ou plus** et `pip`

## 2. Configuration du fichier `.env`

Docker Compose lit un fichier `.env` à la racine du projet. Il n'est **pas versionné** (il est dans `.gitignore`) : il faut le créer à partir du modèle.

    cp .env.example .env

Variables obligatoires (présentes dans `.env.example`) :

| Variable | Rôle |
|---|---|
| `POSTGRES_DB` | Nom de la base (ex. `yummy_db`) |
| `POSTGRES_USER` | Utilisateur PostgreSQL (ex. `yummy_user`) |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL : remplacez `change_me` |

Variables optionnelles à ajouter dans `.env` selon vos besoins :

| Variable | Rôle |
|---|---|
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Compte gérant créé au premier démarrage s'il n'existe pas. Sans elles, aucun compte n'est créé. |
| `SECRET_KEY` | Clé qui signe les cookies de session. Mettez une longue chaîne aléatoire. |
| `DEMO_DATA` | À `1` : charge le menu avec photos et des données de démonstration. |
| `DELIVERY_FEE` | Frais de livraison en DA (200 par défaut). |

`DATABASE_URL` et `REDIS_URL` n'ont pas besoin d'être écrites dans `.env` : `docker-compose.yml` les construit pour le service `app`.

## 3. Démarrer le projet avec Docker Compose

    docker compose up --build -d

Cette commande construit l'image de l'application et démarre 4 conteneurs. Au premier démarrage, PostgreSQL charge automatiquement le schéma `db/init.sql`.

Vérifier l'état des conteneurs :

    docker compose ps

Les 4 services doivent être `Up` (`db` doit être `healthy`). En cas de problème :

    docker compose logs
    docker compose logs app --tail=50

Arrêter les services (en gardant la base) :

    docker compose down

## 4. Services et ports

| Service | Conteneur | Rôle | Adresse sur votre machine |
|---|---|---|---|
| `nginx` | `yummy_nginx` | Reverse proxy, **point d'entrée recommandé** | http://localhost:**8080** |
| `app` | `yummy_app` | API FastAPI et site web | http://localhost:8000 |
| `db` | `yummy_postgres` | PostgreSQL | localhost:5433 |
| `redis` | `yummy_redis` | Redis (Pub/Sub du WebSocket) | localhost:6380 |

Les ports de PostgreSQL (5433) et de Redis (6380) sont volontairement différents des ports par défaut (5432 et 6379), pour éviter les conflits avec une instance déjà installée sur votre machine.

Nginx écoute sur le port 80 du conteneur, exposé en **8080** sur votre machine. Il transmet toutes les requêtes (y compris le WebSocket) à `app:8000`.

## 5. Accéder à l'application

Par Nginx (recommandé) :

* Site client : http://localhost:8080/
* Espace du personnel : http://localhost:8080/admin/login.html
* Documentation interactive de l'API : http://localhost:8080/docs
* Page de test WebSocket : http://localhost:8080/ws-test

Directement sur l'application (sans Nginx) : mêmes adresses avec le port `8000`.

## 6. Vérifier `/health` à travers Nginx

    curl -i http://localhost:8080/health

Réponse attendue :

    HTTP/1.1 200 OK
    Server: nginx/1.27...
    {"status":"OK","database":"connected"}

* `200` et `"database":"connected"` : FastAPI répond et PostgreSQL est joignable.
* `Server: nginx` : la réponse est bien passée par le reverse proxy.
* Si la base est injoignable, la route répond `503`.

## 7. Exécuter les tests Pytest

Les tests utilisent une vraie base PostgreSQL et Redis. Démarrez-les, puis lancez Pytest depuis la racine du projet :

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

    docker compose up -d db redis

    PYTHONPATH=. \
    DATABASE_URL=postgresql://yummy_user:yummy_password@localhost:5433/yummy_db \
    REDIS_URL=redis://localhost:6380 \
    python -m pytest -q

Adaptez `yummy_user`, `yummy_password` et `yummy_db` aux valeurs de votre `.env`. Pour un seul fichier :

    ... python -m pytest tests/test_auth_roles.py -v

Contenu de `tests/` :

| Fichier | Contenu |
|---|---|
| `test_admin.py`, `test_commandes.py` | Interface gérant et commandes clients |
| `test_auth_roles.py` | Authentification, sessions, droits par rôle |
| `test_menu_crud.py` | CRUD des plats : codes HTTP, validation, erreurs, 404 et 409 |
| `test_websocket.py` | Route WebSocket `/ws` (ping/pong, diffusion, déconnexion) |
| `test_redis_websocket.py` | Un message publié dans Redis arrive au client WebSocket |

Note : deux tests de `test_websocket.py` sont marqués `xfail` (échec connu du client de test à la fermeture de la connexion, non observé en conditions réelles).

## 8. Vérifier la configuration Nginx

Vérification de la syntaxe, sans démarrer le projet :

    docker run --rm --add-host app:127.0.0.1 \
      -v "$PWD/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
      nginx:1.27-alpine nginx -t

Réponse attendue : `syntax is ok` et `test is successful`.

L'option `--add-host app:127.0.0.1` est nécessaire : la configuration contient `app:8000`, et Nginx refuse de valider un hôte qui n'existe pas.

## 9. Intégration continue (GitHub Actions)

Le workflow `.github/workflows/ci.yml` se lance sur chaque push et Pull Request vers `main`. Il contient deux jobs :

* **`test-backend`** : démarre PostgreSQL et Redis comme services, charge `db/init.sql`, puis lance Pytest.
* **`nginx-check`** : vérifie la syntaxe Nginx (`nginx -t`), démarre la stack avec Docker Compose et teste `/health` à travers Nginx.

## 10. Réinitialiser l'environnement

Le schéma `db/init.sql` n'est chargé que si le volume PostgreSQL est vide. Après une modification du schéma :

    docker compose down -v
    docker compose up --build -d

Attention : `-v` **supprime les données** de la base et les photos envoyées.