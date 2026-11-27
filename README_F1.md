# F1 — Suivi des commandes, annulation et estimation du temps de préparation

Ce document décrit l’implémentation de la fonctionnalité F1 du projet Yummy DevOps.

## 1. Périmètre de la fonctionnalité

La fonctionnalité F1 concerne le suivi des commandes par le client :

- Le client peut annuler une commande uniquement lorsque son statut est `recue` (affiché **Reçue** dans l’interface).
- Lorsqu’une commande éligible est annulée, un paiement en ligne déjà marqué comme payé est remboursé par la logique commune de changement de statut. Une commande payée en espèces n’est pas indiquée à tort comme remboursée.
- Le temps de préparation estimé reste masqué jusqu’à ce que le statut de la commande passe à `en_preparation`.
- L’estimation est calculée à partir des temps de préparation (`plats.temps_preparation`) et des quantités enregistrées dans les lignes de commande. Le cuisinier n’a pas à saisir manuellement cette estimation.

La fonctionnalité F1 ne modifie volontairement pas `app/routers/commandes.py`, `app/order_status.py`, `app/main.py` ni `tests/conftest.py`. Le routeur de suivi a déjà été enregistré lors de la mise en place de F0, le module commun de gestion des statuts centralise les transitions et les règles de remboursement, et les fixtures de test communes sont réutilisées.

## 2. Calcul du temps de préparation : préparation en parallèle

Multiplier directement le temps de préparation d’un plat par sa quantité donnerait une estimation peu réaliste lorsque plusieurs unités identiques peuvent être préparées en même temps. F1 repose donc sur les hypothèses initiales de capacité suivantes :

| Poste de préparation | Nombre maximal d’articles préparés simultanément | Reconnaissance de la catégorie |
|---|---:|---|
| Plats / nourriture | 5 | Toutes les catégories, sauf une catégorie reconnue comme étant celle des boissons |
| Boissons | 4 | `Boissons`, sans distinction entre majuscules et minuscules ; `Boisson`, `Drink` et `Drinks` sont également reconnus |

`temps_preparation` représente le temps estimé, en minutes, nécessaire pour préparer une unité de cet article du menu. Chaque unité commandée occupe un emplacement de préparation en parallèle pendant cette durée. Pour chaque poste, F1 affecte d’abord les tâches les plus longues à l’emplacement actuellement le moins chargé. Cette méthode simple de planification prend en compte les durées différentes des articles tout en respectant la capacité du poste.

On suppose que les plats et les boissons sont préparés simultanément dans deux postes distincts. Par conséquent, le temps estimé pour la commande est :

```text
estimated_order_minutes = max(food_station_minutes, drinks_station_minutes)
```

### Exemples

| Commande | Estimation | Explication |
|---|---:|---|
| 4 burgers de 15 minutes chacun | 15 minutes | Les quatre burgers tiennent dans les cinq emplacements disponibles ; les durées ne sont pas additionnées (4 × 15) |
| 6 plats de 12 minutes chacun | 24 minutes | Cinq plats commencent en même temps ; le sixième commence lorsqu’un emplacement se libère |
| 5 boissons de 3 minutes chacune | 6 minutes | Quatre boissons commencent en même temps ; la cinquième est préparée lors du cycle suivant |
| 5 plats de 15 minutes + 4 boissons de 3 minutes | 15 minutes | Les plats et les boissons sont préparés en parallèle ; le poste le plus lent détermine l’estimation |

Les capacités sont définies par les constantes suivantes dans `app/routers/suivi.py` :

- `CAPACITE_PLATS_EN_PARALLELE = 5`
- `CAPACITE_BOISSONS_EN_PARALLELE = 4`

Elles peuvent être ajustées si l’équipe valide d’autres hypothèses concernant l’organisation de la cuisine. Les boissons sont identifiées à partir du nom de leur catégorie dans le menu. La catégorie des boissons doit donc conserver le nom `Boissons` (ou l’un des noms reconnus). À l’avenir, un type de catégorie défini directement dans la base de données serait plus fiable si les noms des catégories deviennent librement modifiables.

### Limite importante

Cette estimation concerne uniquement les articles d’**une seule commande**. Elle ne prend pas encore en compte les autres commandes qui occupent déjà la cuisine, la disponibilité réelle du personnel, les contraintes liées aux équipements ou une file d’attente globale en cuisine. Il s’agit donc d’une estimation au niveau de la commande, et non d’une heure de livraison garantie ou d’un compte à rebours en temps réel. La gestion partagée de la capacité de la cuisine et de sa file d’attente pourrait faire l’objet d’une amélioration ultérieure.

## 3. Modifications du backend

### `app/routers/suivi.py`

Le routeur F1 expose deux points d’accès (endpoints) :

| Méthode | Endpoint | Rôle |
|---|---|---|
| `GET` | `/api/suivi/{token}/temps-attente` | Renvoie l’estimation du temps de préparation uniquement lorsque la commande est au statut `en_preparation` |
| `POST` | `/api/suivi/{token}/annuler` | Tente d’annuler la commande du client à l’aide de son jeton privé de suivi |

Exemple de réponse pour le temps d’attente avant le début de la préparation :

```json
{
  "visible": false,
  "temps_attente_minutes": null
}
```

Exemple de réponse lorsque la commande est en préparation :

```json
{
  "visible": true,
  "temps_attente_minutes": 15
}
```

Les UUID invalides et les jetons de suivi inconnus renvoient une réponse `404`.

Le point d’accès d’annulation recherche la commande à l’aide de `suivi_token`, puis délègue le changement de statut à la fonction suivante :

```python
change_status(cur, order["id"], "annulee", CLIENT)
```

Il ne modifie pas directement `commandes.statut`. La fonction commune `change_status()` vérifie que le statut actuel est `recue`, verrouille la ligne de commande, enregistre l’historique du statut et applique la règle de remboursement existante pour les paiements en ligne. Une annulation après le début de la préparation est refusée (`409`).

## 4. Modifications du frontend

### `frontend/suivi.html`

Charge la feuille de style de la page de suivi ainsi que le JavaScript destiné au suivi des commandes par le client.

### `frontend/assets/js/public/tracking.js`

- Charge les informations de la commande à l’aide du point d’accès de suivi client déjà existant.
- Affiche le bouton **Annuler ma commande** uniquement lorsque le statut actuel est `recue`.
- Demande au client de confirmer l’annulation avant de l’envoyer.
- Appelle le point d’accès d’annulation de F1, puis recharge les informations de suivi après une annulation réussie.
- Interroge le point d’accès du temps d’attente uniquement lorsque le statut est `en_preparation`.
- Affiche l’estimation uniquement pendant la préparation de la commande.
- Conserve l’actualisation existante du suivi toutes les cinq secondes pour les commandes qui ne sont pas dans un état final.

### `frontend/assets/js/public/checkout.js`

- Ajoute une zone consacrée au temps d’attente dans la fenêtre de confirmation **Commande envoyée !**, juste après le numéro de commande, le total et le mode de paiement.
- Affiche initialement le message : **Disponible dès que votre commande passe en préparation.** Cette règle garantit que l’estimation numérique reste masquée tant que la commande est uniquement au statut `recue`.
- Vérifie le statut de la commande toutes les cinq secondes tant que la fenêtre de confirmation reste ouverte.
- Dès que le statut passe à `en_preparation`, demande l’estimation F1 et remplace le message initial par le temps estimé en minutes.
- Arrête les vérifications lorsque la fenêtre est fermée ou lorsque la commande dépasse l’étape de préparation.
- Si le client ferme la fenêtre, la page de suivi indépendante continue d’afficher l’estimation lorsque la préparation commence.

### `frontend/assets/css/public.css`

Ajoute les styles de la zone du temps d’attente dans la fenêtre de confirmation de l’envoi de la commande.

### `frontend/assets/css/tracking.css`

Ajoute les styles des informations sur le temps d’attente et de la zone d’annulation.

## 5. Modifications des tests

Un nouveau fichier, `tests/test_suivi.py`, contient les tests propres à F1. Il réutilise les fixtures `anon`, `make_order`, `make_plat`, `get_order` et `get_history` définies dans `tests/conftest.py`. Aucun helper de création de données de test en double n’est ajouté.

| Test | Vérification effectuée |
|---|---|
| `test_wait_time_is_hidden_before_preparation` | Vérifie que l’estimation reste masquée tant que la commande est au statut `recue` |
| `test_wait_time_prepares_four_identical_food_items_in_parallel` | Vérifie que quatre articles alimentaires de 15 minutes prennent 15 minutes, et non 60 |
| `test_wait_time_uses_five_parallel_food_slots` | Vérifie que six articles alimentaires de 12 minutes prennent 24 minutes avec cinq emplacements en parallèle |
| `test_wait_time_uses_four_parallel_drink_slots` | Vérifie que cinq boissons de 3 minutes prennent 6 minutes avec quatre emplacements en parallèle |
| `test_food_and_drinks_are_prepared_at_the_same_time` | Vérifie que les plats et les boissons sont préparés en parallèle et que leurs durées ne sont pas additionnées |
| `test_wait_time_rejects_unknown_or_invalid_token` | Vérifie que les jetons de suivi invalides ou inconnus renvoient `404` |
| `test_customer_can_cancel_received_order_and_online_payment_is_refunded` | Vérifie que le client peut annuler une commande reçue payée en ligne et que le paiement est remboursé |
| `test_customer_can_cancel_cash_order_without_changing_payment_state` | Vérifie que l’annulation d’une commande payée en espèces ne la marque pas comme un remboursement en ligne |
| `test_customer_cannot_cancel_after_preparation_has_started` | Vérifie qu’une commande en cours de préparation ne peut plus être annulée par le client (`409`) |
| `test_cancel_rejects_unknown_or_invalid_token` | Vérifie que les jetons invalides ou inconnus ne permettent pas l’annulation et renvoient `404` |
| `test_tracking_page_and_its_assets_are_served` | Vérifie que la page de suivi HTML, le JavaScript et les fichiers CSS sont bien servis |
| `test_checkout_confirmation_shows_wait_time_after_order_summary` | Vérifie que la fenêtre de confirmation affiche la zone du temps d’attente après le récapitulatif de commande et interroge les points d’accès de suivi et d’estimation |

Les tests d’intégration liés aux boissons utilisent la catégorie `Boissons` initialisée dans la base de données du projet.

## 6. Exécution des tests

Depuis la racine du dépôt, activez l’environnement virtuel du projet, vérifiez que la base de données PostgreSQL de test est démarrée et initialisée, puis configurez la même variable `DATABASE_URL` que celle utilisée par les autres tests d’intégration du projet.

Pour exécuter uniquement les tests F1 :

```bash
python -m pytest tests/test_suivi.py -v
```

Pour exécuter toute la suite de tests du backend :

```bash
python -m pytest -q
```

Pour vérifier la syntaxe Python :

```bash
python -m compileall -q app/routers/suivi.py tests/test_suivi.py
```

Les tests nécessitent la base de données du projet. Une simple vérification statique de la syntaxe ne permet pas de confirmer le bon fonctionnement avec la base de données.

## 7. Fichiers inclus dans F1

| Fichier | Modification |
|---|---|
| `app/routers/suivi.py` | Implémente la validation des jetons, le point d’accès d’annulation client, le calcul du temps d’attente en parallèle et le point d’accès d’estimation |
| `frontend/suivi.html` | Intègre les ressources nécessaires à la page de suivi |
| `frontend/assets/js/public/tracking.js` | Ajoute l’affichage conditionnel de l’annulation et du temps d’attente |
| `frontend/assets/css/tracking.css` | Met en forme les zones du temps d’attente et de l’annulation sur la page de suivi |
| `frontend/assets/js/public/checkout.js` | Ajoute le message initial et l’estimation actualisée dans la fenêtre « Commande envoyée ! » |
| `frontend/assets/css/public.css` | Met en forme la zone du temps d’attente dans la fenêtre de confirmation |
| `tests/test_suivi.py` | Ajoute les tests des endpoints F1, du calcul, de l’annulation, des ressources de suivi et de la fenêtre de confirmation |
| `docs/README-F1.md` | Documente la logique F1, les hypothèses, les endpoints, les fichiers et les tests |

## 8. Limites de F1 et consignes de collaboration

- Conservez cette fonctionnalité dans sa propre branche et soumettez-la via une Pull Request (demande de fusion).
- Demandez à un autre membre de l’équipe de vérifier la Pull Request et ne procédez à la fusion que lorsque les vérifications CI requises sont réussies.
- Continuez à utiliser `app/order_status.py` et `change_status()` pour chaque changement de statut d’une commande.
- Continuez à utiliser `tests/conftest.py` pour les fixtures de test communes.
- Ne modifiez pas `commandes.py` : le suivi des commandes côté client pour F1 doit rester dans le routeur dédié `suivi`.
- N’ajoutez pas d’enregistrement du routeur dans `app/main.py` : cette étape a déjà été réalisée dans F0.