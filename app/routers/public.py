from fastapi import APIRouter
from app.db import cursor

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/menu")
def menu():
    """Menu client : catégories et plats non archivés (les plats indisponibles sont renvoyés pour être grisés)."""
    with cursor() as cur:
        cur.execute("""
            SELECT c.id AS cat_id, c.nom AS cat_nom, p.id, p.nom, p.description, p.prix::float AS prix,
                   p.photo_url, p.temps_preparation, p.disponible
            FROM categories c LEFT JOIN plats p ON p.categorie_id = c.id AND NOT p.archive
            ORDER BY c.ordre, c.id, p.nom""")
        rows = cur.fetchall()
    cats = {}
    for r in rows:
        c = cats.setdefault(r["cat_id"], {"id": r["cat_id"], "nom": r["cat_nom"], "plats": []})
        if r["id"]:
            c["plats"].append({k: r[k] for k in ("id", "nom", "description", "prix", "photo_url", "temps_preparation", "disponible")})
    return [c for c in cats.values() if c["plats"]]
