"""Routes for creating customer orders and retrieving them with a tracking token."""
import os, re, time, uuid
from collections import defaultdict
from decimal import Decimal
from typing import Literal, Optional
import psycopg2.errors as pgerr
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from app import config
from app.db import cursor

router = APIRouter(prefix="/api", tags=["commandes"])
RATE = int(os.getenv("ORDER_RATE_LIMIT", "10"))  # commandes max par minute et par adresse IP
_hits = defaultdict(list)
PHONE = re.compile(r"^[0-9+ ().-]{8,20}$")


def _limit(request: Request):
    ip, now = request.client.host if request.client else "?", time.time()
    _hits[ip] = [t for t in _hits[ip] if now - t < 60]
    if len(_hits[ip]) >= RATE:
        raise HTTPException(429, "Trop de commandes en peu de temps, réessayez dans une minute")
    _hits[ip].append(now)


class LigneIn(BaseModel):
    plat_id: int
    quantite: int = Field(ge=1, le=20)
    commentaire: Optional[str] = Field(None, max_length=200)


class CommandeIn(BaseModel):
    mode: Literal["sur_place", "a_emporter", "livraison"]
    table_numero: Optional[int] = None
    client_nom: Optional[str] = Field(None, max_length=100)
    client_telephone: Optional[str] = Field(None, max_length=30)
    adresse_livraison: Optional[str] = Field(None, max_length=300)
    note: Optional[str] = Field(None, max_length=500)
    paiement_mode: Literal["especes", "en_ligne"] = "especes"  # aucune donnée de carte n'est reçue ni stockée
    lignes: list[LigneIn] = Field(min_length=1, max_length=30)


@router.get("/options-commande")
def options():
    with cursor() as cur:
        cur.execute("SELECT numero FROM tables_restaurant WHERE active ORDER BY numero")
        return {"frais_livraison": config.DELIVERY_FEE, "tables": [r["numero"] for r in cur.fetchall()]}


@router.post("/commandes", status_code=201)
def creer_commande(b: CommandeIn, request: Request):
    _limit(request)
    nom, tel, adr = (b.client_nom or "").strip(), (b.client_telephone or "").strip(), (b.adresse_livraison or "").strip()
    if b.mode == "sur_place" and not b.table_numero:
        raise HTTPException(422, "Choisissez votre numéro de table")
    if b.mode in ("a_emporter", "livraison"):
        if not nom:
            raise HTTPException(422, "Indiquez votre nom")
        if not PHONE.match(tel):
            raise HTTPException(422, "Numéro de téléphone invalide")
    if b.mode == "livraison" and len(adr) < 5:
        raise HTTPException(422, "Indiquez votre adresse de livraison")
    qty, comment = defaultdict(int), {}
    for l in b.lignes:  # un même plat ajouté deux fois est regroupé
        qty[l.plat_id] += l.quantite
        if l.commentaire and l.commentaire.strip():
            comment.setdefault(l.plat_id, l.commentaire.strip())
    if any(q > 20 for q in qty.values()):
        raise HTTPException(422, "20 portions maximum par plat")
    try:
        with cursor() as cur:
            table_id = None
            if b.mode == "sur_place":
                cur.execute("SELECT id FROM tables_restaurant WHERE numero = %s AND active", (b.table_numero,))
                t = cur.fetchone()
                if not t:
                    raise HTTPException(422, "Table inconnue")
                table_id = t["id"]
            cur.execute("SELECT id, nom, prix, disponible, archive FROM plats WHERE id = ANY(%s)", (list(qty),))
            found = {r["id"]: r for r in cur.fetchall()}  # les prix viennent TOUJOURS de la base, jamais du navigateur
            for pid in qty:
                p = found.get(pid)
                if not p or p["archive"]:
                    raise HTTPException(409, "Un plat de votre panier n'existe plus : actualisez la page")
                if not p["disponible"]:
                    raise HTTPException(409, f"« {p['nom']} » n'est plus disponible")
            cur.execute("""INSERT INTO commandes (mode, table_id, client_nom, client_telephone, adresse_livraison, note, paiement_mode)
                           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, numero, suivi_token""",
                        (b.mode, table_id, nom or None, tel or None, adr if b.mode == "livraison" else None, (b.note or "").strip() or None, b.paiement_mode))
            cmd, sous = cur.fetchone(), Decimal(0)
            for pid, q in qty.items():
                p = found[pid]; ligne = p["prix"] * q; sous += ligne
                cur.execute("""INSERT INTO lignes_commande (commande_id, plat_id, nom_plat, prix_unitaire, quantite, total_ligne, commentaire)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)""", (cmd["id"], pid, p["nom"], p["prix"], q, ligne, comment.get(pid)))
            frais = Decimal(config.DELIVERY_FEE) if b.mode == "livraison" else Decimal(0)
            paiement = "paye" if b.paiement_mode == "en_ligne" else "en_attente"  # passerelle simulée : toujours validée
            cur.execute("UPDATE commandes SET sous_total = %s, frais_livraison = %s, total = %s, paiement_statut = %s WHERE id = %s",
                        (sous, frais, sous + frais, paiement, cmd["id"]))
    except pgerr.RaiseException as e:  # règles des triggers SQL
        raise HTTPException(409, e.diag.message_primary or "Commande refusée")
    return {"numero": cmd["numero"], "suivi_token": cmd["suivi_token"], "statut": "recue", "mode": b.mode,
            "paiement_mode": b.paiement_mode, "paiement_statut": paiement, "sous_total": float(sous), "frais_livraison": float(frais), "total": float(sous + frais)}


@router.get("/commandes/suivi/{token}")
def suivi(token: str):
    try:
        uuid.UUID(token)
    except ValueError:
        raise HTTPException(404, "Commande introuvable")
    with cursor() as cur:
        cur.execute("""SELECT c.id, c.numero, c.mode::text AS mode, c.statut::text AS statut, t.numero AS table_numero, c.note,
                              c.paiement_mode::text AS paiement_mode, c.paiement_statut::text AS paiement_statut,
                              c.sous_total::float AS sous_total, c.frais_livraison::float AS frais_livraison, c.total::float AS total, c.created_at
                       FROM commandes c LEFT JOIN tables_restaurant t ON t.id = c.table_id WHERE c.suivi_token = %s""", (token,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(404, "Commande introuvable")
        cur.execute("SELECT nom_plat AS nom, quantite, total_ligne::float AS total, commentaire FROM lignes_commande WHERE commande_id = %s ORDER BY id", (c.pop("id"),))
        c["lignes"] = cur.fetchall()
    return c
