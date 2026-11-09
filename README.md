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

### Lancer le projet en local (Docker)

**Prérequis :** Docker avec Docker Compose installé.

**1. Cloner le dépôt**

    git clone https://github.com/Malaktk5/CyberV-MenuApp.git
    cd CyberV-MenuApp

**2. Construire et démarrer tous les services**

    docker compose up --build -d

Cette commande démarre 3 conteneurs : l'application FastAPI, PostgreSQL et Redis.

**3. Vérifier que tout tourne**

    docker compose ps
    curl http://localhost:8000/health

La deuxième commande doit répondre `{"status":"OK"}`. 

**4. Arrêter les services**

    docker compose down

**Ports utilises**

| Service | Adresse |
|---|---|
| API FastAPI | localhost:8000 |
| PostgreSQL | localhost:5433 |
| Redis | localhost:6380 |

the ports used in this configuration are different than the default ports to avoid any conflict if theres instances of redis/postgres in the ports already
