"""F2: kitchen order screen."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db import cursor
from app.order_status import change_status
from app.security import require_role

router = APIRouter(prefix="/api/cuisine", tags=["cuisine"])

COOK_ONLY = Depends(require_role("cuisinier"))


class StatusPayload(BaseModel):
    statut: str


@router.get("/commandes")
def list_kitchen_orders(_user=COOK_ONLY):
    """Liste les commandes actives (reçues et en préparation), les plus anciennes en premier."""
    with cursor() as cur:
        cur.execute(
            """
            SELECT c.id, c.numero, c.mode::text AS mode, c.statut::text AS statut,
                   c.note, c.created_at, t.numero AS table_numero
            FROM commandes c
            LEFT JOIN tables_restaurant t ON t.id = c.table_id
            WHERE c.statut IN ('recue', 'en_preparation')
              AND c.mode IN ('sur_place', 'a_emporter')
            ORDER BY c.created_at ASC, c.id ASC
            """
        )
        orders = cur.fetchall()
        if not orders:
            return []

        order_ids = [o["id"] for o in orders]
        cur.execute(
            """
            SELECT id, commande_id, nom_plat, quantite, commentaire
            FROM lignes_commande
            WHERE commande_id = ANY(%s)
            ORDER BY id ASC
            """,
            (order_ids,),
        )
        lines_by_order = {}
        for line in cur.fetchall():
            lines_by_order.setdefault(line["commande_id"], []).append(line)

        for o in orders:
            o["lignes"] = lines_by_order.get(o["id"], [])
        return orders


@router.post("/commandes/{order_id}/statut")
def update_kitchen_status(order_id: int, body: StatusPayload, user=COOK_ONLY):
    """Fait passer une commande de reçue -> en_preparation -> prete."""
    if body.statut not in ("en_preparation", "prete"):
        raise HTTPException(422, "Transition non autorisée depuis la cuisine")
    with cursor() as cur:
        return change_status(cur, order_id, body.statut, user)
