# CyberV-MenuApp

**Thème 15 :** Commandes de restaurant

**Équipe :** CyberV (Zemmour Sihame, Moad Kenza, Saadi Ameterrahmane, Touafek Malak)

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
