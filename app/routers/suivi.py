"""F1: customer order tracking, cancellation, and preparation-time estimate."""
from uuid import UUID
import unicodedata

from fastapi import APIRouter, HTTPException

from app.db import cursor
from app.order_status import CLIENT, change_status

router = APIRouter(prefix="/api/suivi", tags=["suivi"])

# Assumed preparation capacity for one customer's order.
CAPACITE_PLATS_EN_PARALLELE = 5
CAPACITE_BOISSONS_EN_PARALLELE = 4
CATEGORIES_BOISSONS = {"boisson", "boissons", "drink", "drinks"}


def _validated_token(token: str) -> str:
    """Return a normalized UUID token or the same 404 used for unknown orders."""
    try:
        return str(UUID(token))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(status_code=404, detail="Commande introuvable")


def _normaliser_categorie(value: str | None) -> str:
    """Normalize a category label so Boissons/boissons are treated equally."""
    value = value or ""
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char)).strip().casefold()


def _temps_sur_postes_paralleles(durees: list[int], capacite: int) -> int:
    """Estimate the completion time using identical parallel preparation slots.

    Long jobs are assigned first to the currently least-loaded slot. This is a
    lightweight scheduling heuristic; it avoids multiplying the time of items
    that can be prepared at the same time.
    """
    if not durees:
        return 0

    if capacite < 1:
        raise ValueError("La capacité parallèle doit être supérieure à zéro")

    nombre_postes = min(capacite, len(durees))
    charges = [0] * nombre_postes

    for duree in sorted((max(0, int(value)) for value in durees), reverse=True):
        poste = min(range(nombre_postes), key=charges.__getitem__)
        charges[poste] += duree

    return max(charges)


def calculer_temps_attente(cur, commande_id: int) -> int:
    """Estimate order preparation time with separate food and drink capacities.

    Up to five food units and four drink units can be prepared simultaneously.
    Drinks are recognized by the category named "Boissons" (case-insensitive).
    Food and drink stations work in parallel, so the order estimate is the
    slower of the two station completion times.
    """
    cur.execute(
        """SELECT c.nom AS categorie, p.temps_preparation, lc.quantite
           FROM lignes_commande AS lc
           JOIN plats AS p ON p.id = lc.plat_id
           JOIN categories AS c ON c.id = p.categorie_id
           WHERE lc.commande_id = %s""",
        (commande_id,),
    )

    temps_plats = []
    temps_boissons = []
    for line in cur.fetchall():
        destination = (
            temps_boissons
            if _normaliser_categorie(line["categorie"]) in CATEGORIES_BOISSONS
            else temps_plats
        )
        duree = max(0, int(line["temps_preparation"] or 0))
        quantite = max(0, int(line["quantite"] or 0))
        destination.extend([duree] * quantite)

    attente_plats = _temps_sur_postes_paralleles(
        temps_plats, capacite=CAPACITE_PLATS_EN_PARALLELE
    )
    attente_boissons = _temps_sur_postes_paralleles(
        temps_boissons, capacite=CAPACITE_BOISSONS_EN_PARALLELE
    )

    # Food and drinks are assumed to be prepared at the same time.
    return max(attente_plats, attente_boissons)


@router.get("/{token}/temps-attente")
def obtenir_temps_attente(token: str):
    """Expose the estimate only after the kitchen moves the order to preparation."""
    token = _validated_token(token)

    with cursor() as cur:
        cur.execute(
            """SELECT id, statut::text AS statut
               FROM commandes
               WHERE suivi_token = %s""",
            (token,),
        )
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Commande introuvable")

        if order["statut"] != "en_preparation":
            return {"visible": False, "temps_attente_minutes": None}

        minutes = calculer_temps_attente(cur, order["id"])

    return {"visible": True, "temps_attente_minutes": minutes}


@router.post("/{token}/annuler")
def annuler_commande_client(token: str):
    """Cancel an order through its private tracking token, as an anonymous client."""
    token = _validated_token(token)

    with cursor() as cur:
        cur.execute(
            "SELECT id FROM commandes WHERE suivi_token = %s",
            (token,),
        )
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Commande introuvable")

        # change_status locks the row, checks that it is still "recue", and
        # automatically marks an online payment as refunded when appropriate.
        return change_status(cur, order["id"], "annulee", CLIENT)