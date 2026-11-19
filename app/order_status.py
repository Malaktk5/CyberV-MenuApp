"""Centralizes order status changes and validates them before updating the database.

Kitchen, dining room, delivery, cashier, and customer actions should call
`change_status`; they should not update the `commandes` table directly.
"""

import psycopg2.errors as pgerr
from fastapi import HTTPException

# Anonymous callers represent a customer canceling through a tracking link.
# Routers must look up the order using its `suivi_token` before calling this code.
CLIENT = {"id": None, "role": "client"}

TOUS_MODES = ("sur_place", "a_emporter", "livraison")
SUR_PLACE_OU_EMPORTER = ("sur_place", "a_emporter")
LIVRAISON = ("livraison",)

# Maps (current status, next status) to the roles and order modes that allow the change.
TRANSITIONS = {
    ("recue", "en_preparation"): (("cuisinier",), TOUS_MODES),
    ("en_preparation", "prete"): (("cuisinier",), TOUS_MODES),
    ("prete", "servie"): (("serveur",), SUR_PLACE_OU_EMPORTER),
    ("prete", "en_route"): (("livreur",), LIVRAISON),
    ("en_route", "livree"): (("livreur",), LIVRAISON),
    ("en_route", "echec"): (("livreur",), LIVRAISON),
    ("recue", "annulee"): (("client", "caissier"), TOUS_MODES),
}

STATUTS_FR = {"recue": "reçue", "en_preparation": "en préparation", "prete": "prête", "servie": "servie",
              "en_route": "en route", "livree": "livrée", "echec": "en échec", "annulee": "annulée",
              "remboursee": "remboursée"}
MODES_FR = {"sur_place": "sur place", "a_emporter": "à emporter", "livraison": "livraison"}


def change_status(cur, order_id: int, new_status: str, actor: dict, motif: str | None = None) -> dict:
    """Passe la commande `order_id` à `new_status` au nom de `actor` ({"id": ..., "role": ...}).

    Renvoie {id, numero, mode, ancien_statut, statut, paiement_statut}.
    Annuler une commande payée en ligne la marque aussi « remboursée » (paiement_statut).
    """
    if new_status not in {cible for _, cible in TRANSITIONS}:
        raise HTTPException(422, "Statut demandé invalide")
    roles_vers_cible = {r for (_, cible), (roles, _) in TRANSITIONS.items() if cible == new_status for r in roles}
    if actor["role"] not in roles_vers_cible:  # avant toute lecture : un rôle non autorisé n'apprend rien sur la commande
        raise HTTPException(403, "Accès refusé pour votre rôle")

    # FOR UPDATE : deux clics (ou deux écrans) en même temps ne peuvent pas appliquer le même passage deux fois.
    cur.execute("""SELECT id, numero, mode::text AS mode, statut::text AS statut, paiement_statut::text AS paiement_statut, livreur_id
                   FROM commandes WHERE id = %s FOR UPDATE""", (order_id,))
    o = cur.fetchone()
    if not o:
        raise HTTPException(404, "Commande introuvable")

    regle = TRANSITIONS.get((o["statut"], new_status))
    if regle is None:
        if new_status == "annulee":
            raise HTTPException(409, "Seules les commandes « reçues » peuvent être annulées")
        raise HTTPException(409, f"Changement impossible : la commande est {STATUTS_FR[o['statut']]}, "
                                 f"elle ne peut pas passer à « {STATUTS_FR[new_status]} »")
    roles, modes = regle
    if actor["role"] not in roles:
        raise HTTPException(403, "Accès refusé pour votre rôle")
    if o["mode"] not in modes:
        raise HTTPException(409, f"Cette étape ne s'applique pas à une commande en mode « {MODES_FR[o['mode']]} »")
    if actor["role"] == "livreur" and o["livreur_id"] != actor["id"]:
        raise HTTPException(403, "Cette livraison ne vous est pas assignée")

    sets, vals = ["statut = %s"], [new_status]
    if new_status == "echec":
        motif = (motif or "").strip()
        if not motif:
            raise HTTPException(422, "Indiquez le motif de l'échec")
        sets.append("motif_echec = %s")
        vals.append(motif)
    if new_status == "annulee" and o["paiement_statut"] == "paye":
        sets.append("paiement_statut = 'rembourse'")  # payée en ligne -> remboursée

    # Qui a fait le changement : lu par le trigger SQL (is_local = true : valable pour cette transaction seulement).
    cur.execute("SELECT set_config('app.employe_id', %s, true)", ("" if actor.get("id") is None else str(actor["id"]),))
    try:
        cur.execute(f"""UPDATE commandes SET {', '.join(sets)} WHERE id = %s
                        RETURNING id, numero, mode::text AS mode, statut::text AS statut, paiement_statut::text AS paiement_statut""",
                    (*vals, order_id))
    except pgerr.RaiseException as e:  # dernier filet : les règles du trigger SQL
        raise HTTPException(409, e.diag.message_primary or "Changement refusé")
    row = cur.fetchone()
    row["ancien_statut"] = o["statut"]
    return row
