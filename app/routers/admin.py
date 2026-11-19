import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
import psycopg2.errors as pgerr
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from app import config
from app.db import cursor
from app.security import hash_password, require_role

Role = Literal["serveur", "cuisinier", "caissier", "livreur", "gerant"]
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_role("gerant"))])
staff = APIRouter(prefix="/api/staff", tags=["staff"])  # accessible aussi au cuisinier


# ---------- modèles ----------
class CategorieIn(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    ordre: int = 0


class PlatIn(BaseModel):
    categorie_id: int
    nom: str = Field(min_length=1, max_length=150)
    description: Optional[str] = None
    prix: float = Field(ge=0)
    photo_url: Optional[str] = None
    temps_preparation: int = Field(10, ge=0)
    disponible: bool = True

    @field_validator("photo_url")
    @classmethod
    def photo_ok(cls, v):
        if v and not v.startswith(("/uploads/", "/assets/img/", "http://", "https://")):
            raise ValueError("URL de photo invalide")
        return v or None


class Dispo(BaseModel):
    disponible: bool


class EmployeIn(BaseModel):
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    telephone: Optional[str] = None
    mot_de_passe: str = Field(min_length=8)
    role: Role


class EmployeUpdate(BaseModel):
    actif: Optional[bool] = None
    role: Optional[Role] = None
    mot_de_passe: Optional[str] = Field(None, min_length=8)


# ---------- catégories ----------
@router.get("/categories")
def list_categories():
    with cursor() as cur:
        cur.execute("""SELECT c.id, c.nom, c.ordre, count(p.id) FILTER (WHERE NOT p.archive)::int AS nb_plats
                       FROM categories c LEFT JOIN plats p ON p.categorie_id = c.id GROUP BY c.id ORDER BY c.ordre, c.id""")
        return cur.fetchall()


@router.post("/categories", status_code=201)
def create_categorie(b: CategorieIn):
    try:
        with cursor() as cur:
            cur.execute("INSERT INTO categories (nom, ordre) VALUES (%s, %s) RETURNING id, nom, ordre", (b.nom.strip(), b.ordre))
            return cur.fetchone()
    except pgerr.UniqueViolation:
        raise HTTPException(409, "Cette catégorie existe déjà")


@router.put("/categories/{cid}")
def update_categorie(cid: int, b: CategorieIn):
    try:
        with cursor() as cur:
            cur.execute("UPDATE categories SET nom = %s, ordre = %s WHERE id = %s RETURNING id, nom, ordre", (b.nom.strip(), b.ordre, cid))
            row = cur.fetchone()
    except pgerr.UniqueViolation:
        raise HTTPException(409, "Cette catégorie existe déjà")
    if not row:
        raise HTTPException(404, "Catégorie introuvable")
    return row


@router.delete("/categories/{cid}", status_code=204)
def delete_categorie(cid: int):
    try:
        with cursor() as cur:
            cur.execute("DELETE FROM categories WHERE id = %s", (cid,))
            if cur.rowcount == 0:
                raise HTTPException(404, "Catégorie introuvable")
    except pgerr.ForeignKeyViolation:
        raise HTTPException(409, "Catégorie non vide : déplacez ou supprimez ses plats d'abord")


# ---------- plats ----------
PLAT_SQL = """SELECT p.id, p.categorie_id, c.nom AS categorie, p.nom, p.description, p.prix::float AS prix, p.photo_url,
                     p.temps_preparation, p.disponible, p.archive
              FROM plats p JOIN categories c ON c.id = p.categorie_id"""


def _plat(cur, pid):
    cur.execute(PLAT_SQL + " WHERE p.id = %s", (pid,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Plat introuvable")
    return row


@router.get("/plats")
def list_plats(archives: bool = False):
    with cursor() as cur:
        cur.execute(PLAT_SQL + " WHERE (%s OR NOT p.archive) ORDER BY p.archive, c.ordre, p.nom", (archives,))
        return cur.fetchall()


@router.post("/plats", status_code=201)
def create_plat(b: PlatIn):
    try:
        with cursor() as cur:
            cur.execute("""INSERT INTO plats (categorie_id, nom, description, prix, photo_url, temps_preparation, disponible)
                           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                        (b.categorie_id, b.nom.strip(), b.description, b.prix, b.photo_url, b.temps_preparation, b.disponible))
            return _plat(cur, cur.fetchone()["id"])
    except pgerr.ForeignKeyViolation:
        raise HTTPException(422, "Catégorie inconnue")


@router.put("/plats/{pid}")
def update_plat(pid: int, b: PlatIn):
    try:
        with cursor() as cur:
            cur.execute("""UPDATE plats SET categorie_id=%s, nom=%s, description=%s, prix=%s, photo_url=%s,
                           temps_preparation=%s, disponible=%s WHERE id=%s""",
                        (b.categorie_id, b.nom.strip(), b.description, b.prix, b.photo_url, b.temps_preparation, b.disponible, pid))
            return _plat(cur, pid)
    except pgerr.ForeignKeyViolation:
        raise HTTPException(422, "Catégorie inconnue")


@router.post("/plats/{pid}/archiver")
def archiver(pid: int):
    with cursor() as cur:
        cur.execute("UPDATE plats SET archive = TRUE WHERE id = %s", (pid,))
        return _plat(cur, pid)


@router.post("/plats/{pid}/restaurer")
def restaurer(pid: int):
    with cursor() as cur:
        cur.execute("UPDATE plats SET archive = FALSE WHERE id = %s", (pid,))
        return _plat(cur, pid)


@router.delete("/plats/{pid}", status_code=204)
def delete_plat(pid: int):
    try:
        with cursor() as cur:
            cur.execute("DELETE FROM options_plat WHERE plat_id = %s", (pid,))
            cur.execute("DELETE FROM plats WHERE id = %s", (pid,))
            if cur.rowcount == 0:
                raise HTTPException(404, "Plat introuvable")
    except pgerr.ForeignKeyViolation:
        raise HTTPException(409, "Ce plat a déjà été commandé : archivez-le à la place")


@staff.patch("/plats/{pid}/disponibilite")
def set_disponibilite(pid: int, b: Dispo, user=Depends(require_role("gerant", "cuisinier"))):
    """Case à cocher : décochée = plat grisé et non commandable côté client."""
    with cursor() as cur:
        cur.execute("UPDATE plats SET disponible = %s WHERE id = %s AND NOT archive", (b.disponible, pid))
        if cur.rowcount == 0:
            raise HTTPException(404, "Plat introuvable ou archivé")
        return _plat(cur, pid)


# ---------- photos (corps brut de la requête, pas de dépendance multipart) ----------
MAGIC = [(b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpg")]


@router.post("/upload", status_code=201)
async def upload(request: Request):
    if int(request.headers.get("content-length", 0)) > 3_000_000:
        raise HTTPException(413, "Image trop lourde (3 Mo maximum)")
    data = await request.body()
    ext = next((e for m, e in MAGIC if data.startswith(m)), None) or ("webp" if data[:4] == b"RIFF" and data[8:12] == b"WEBP" else None)
    if not ext or len(data) > 3_000_000:
        raise HTTPException(400, "Fichier invalide : PNG, JPEG ou WebP (3 Mo maximum)")
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(12)}.{ext}"
    (config.UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"/uploads/{name}"}


# ---------- employés ----------
@router.get("/employes")
def list_employes():
    with cursor() as cur:
        cur.execute("SELECT id, nom, prenom, email, telephone, role::text AS role, actif FROM employes ORDER BY role, nom")
        rows = cur.fetchall()
    par_role = {r: 0 for r in ("gerant", "cuisinier", "serveur", "caissier", "livreur")}
    for r in rows:
        if r["actif"]:
            par_role[r["role"]] += 1
    return {"total": sum(par_role.values()), "par_role": par_role, "employes": rows}


@router.post("/employes", status_code=201)
def create_employe(b: EmployeIn):
    try:
        with cursor() as cur:
            cur.execute("""INSERT INTO employes (nom, prenom, email, telephone, mot_de_passe_hash, role)
                           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, nom, prenom, email, role::text AS role, actif""",
                        (b.nom.strip(), b.prenom.strip(), b.email.strip().lower(), b.telephone, hash_password(b.mot_de_passe), b.role))
            return cur.fetchone()
    except pgerr.UniqueViolation:
        raise HTTPException(409, "Cet email est déjà utilisé")


@router.patch("/employes/{eid}")
def update_employe(eid: int, b: EmployeUpdate, user=Depends(require_role("gerant"))):
    if eid == user["id"] and (b.actif is False or (b.role and b.role != "gerant")):
        raise HTTPException(409, "Vous ne pouvez pas désactiver ou rétrograder votre propre compte")
    sets, vals = [], []
    if b.actif is not None: sets.append("actif = %s"); vals.append(b.actif)
    if b.role: sets.append("role = %s"); vals.append(b.role)
    if b.mot_de_passe: sets.append("mot_de_passe_hash = %s"); vals.append(hash_password(b.mot_de_passe))
    if not sets:
        raise HTTPException(400, "Rien à modifier")
    with cursor() as cur:
        cur.execute(f"UPDATE employes SET {', '.join(sets)} WHERE id = %s RETURNING id, nom, prenom, email, role::text AS role, actif", (*vals, eid))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Employé introuvable")
    return row


# ---------- tableau de bord ----------
def period_range(period: str, d: Optional[str]):
    base = datetime.strptime(d, "%Y-%m-%d") if d else (datetime.now(config.LOCAL_TZ).replace(tzinfo=None))
    base = base.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        a = base - timedelta(days=base.weekday()); b = a + timedelta(days=7)
    elif period == "month":
        a = base.replace(day=1); b = (a + timedelta(days=32)).replace(day=1)
    elif period == "year":
        a = base.replace(month=1, day=1); b = a.replace(year=a.year + 1)
    else:
        a, b = base, base + timedelta(days=1)
    off = timedelta(hours=config.TZ_HOURS)  # bornes locales -> UTC
    return a, b, (a - off).replace(tzinfo=timezone.utc), (b - off).replace(tzinfo=timezone.utc)


@router.get("/stats")
def stats(period: Literal["day", "week", "month", "year"] = "day", date: Optional[str] = None):
    a, b, ua, ub = period_range(period, date)
    valid = "statut NOT IN ('annulee','remboursee','echec')"
    w = "created_at >= %s AND created_at < %s"
    fmt = {"day": 'HH24"h"', "year": "MM/YYYY"}.get(period, "DD/MM")
    with cursor() as cur:
        cur.execute(f"""SELECT count(*) FILTER (WHERE {valid})::int AS commandes,
                               count(*) FILTER (WHERE NOT ({valid}))::int AS annulees,
                               count(*) FILTER (WHERE statut IN ('servie','livree'))::int AS terminees,
                               coalesce(sum(total) FILTER (WHERE statut IN ('servie','livree')), 0)::float AS ca,
                               (avg(extract(epoch FROM (prete_at - prise_en_charge_at)) / 60)
                                  FILTER (WHERE prete_at IS NOT NULL AND prise_en_charge_at IS NOT NULL AND {valid}))::float AS prep_min
                        FROM commandes WHERE {w}""", (ua, ub))
        k = cur.fetchone()
        cur.execute(f"""SELECT l.nom_plat AS nom, sum(l.quantite)::int AS quantite FROM lignes_commande l
                        JOIN commandes c ON c.id = l.commande_id
                        WHERE c.created_at >= %s AND c.created_at < %s AND c.{valid}
                        GROUP BY l.nom_plat ORDER BY quantite DESC, nom""", (ua, ub))
        plats = cur.fetchall()
        cur.execute(f"SELECT mode::text AS mode, count(*)::int AS n FROM commandes WHERE {w} AND {valid} GROUP BY mode", (ua, ub))
        modes = {r["mode"]: r["n"] for r in cur.fetchall()}
        cur.execute(f"""SELECT extract(hour FROM created_at + make_interval(hours => %s))::int AS h, count(*)::int AS n
                        FROM commandes WHERE {w} AND {valid} GROUP BY h ORDER BY n DESC, h LIMIT 3""", (config.TZ_HOURS, ua, ub))
        pointe = cur.fetchall()
        cur.execute(f"""SELECT to_char(created_at + make_interval(hours => %s), %s) AS label, min(created_at) AS t,
                               count(*)::int AS commandes,
                               coalesce(sum(total) FILTER (WHERE statut IN ('servie','livree')), 0)::float AS ca
                        FROM commandes WHERE {w} AND {valid} GROUP BY label ORDER BY t""", (config.TZ_HOURS, fmt, ua, ub))
        serie = [{"label": r["label"], "commandes": r["commandes"], "ca": r["ca"]} for r in cur.fetchall()]
        cur.execute("SELECT count(*)::int AS n FROM commandes WHERE statut IN ('recue','en_preparation','prete','en_route')")
        en_cours = cur.fetchone()["n"]
        cur.execute("SELECT numero, mode::text AS mode, statut::text AS statut, total::float AS total, created_at FROM commandes ORDER BY created_at DESC LIMIT 6")
        recentes = cur.fetchall()
    total_cmd = k["commandes"] + k["annulees"]
    return {
        "period": period, "debut": a.strftime("%Y-%m-%d"), "fin": (b - timedelta(days=1)).strftime("%Y-%m-%d"),
        "ca": k["ca"], "commandes": k["commandes"], "panier_moyen": round(k["ca"] / k["terminees"]) if k["terminees"] else 0,
        "plats_vendus": sum(p["quantite"] for p in plats), "top_plats": plats[:8],
        "temps_prep_moyen": round(k["prep_min"], 1) if k["prep_min"] is not None else None,
        "annulees": k["annulees"], "taux_annulation": round(100 * k["annulees"] / total_cmd, 1) if total_cmd else 0,
        "modes": modes, "heures_de_pointe": pointe, "serie": serie, "en_cours": en_cours, "recentes": recentes,
    }


# ---------- commandes reçues (onglet « Commandes » du gérant) ----------
GROUPES = {"encours": ("recue", "en_preparation", "prete", "en_route"), "terminees": ("servie", "livree"), "annulees": ("annulee", "echec", "remboursee")}


@router.get("/commandes")
def list_commandes(statut: Literal["encours", "terminees", "annulees", "toutes"] = "encours", q: Optional[str] = None, limit: int = Query(100, ge=1, le=300)):
    where, params = [], []
    if statut != "toutes":
        where.append("c.statut::text = ANY(%s)"); params.append(list(GROUPES[statut]))
    if q and q.strip():
        where.append("(c.numero ILIKE %s OR c.client_nom ILIKE %s)"); params += [f"%{q.strip()}%"] * 2
    sql = f"""SELECT c.id, c.numero, c.mode::text AS mode, c.statut::text AS statut, t.numero AS table_numero, c.client_nom, c.client_telephone,
                     c.adresse_livraison, c.note, c.paiement_mode::text AS paiement_mode, c.paiement_statut::text AS paiement_statut,
                     c.sous_total::float AS sous_total, c.frais_livraison::float AS frais_livraison, c.total::float AS total, c.created_at,
                     coalesce(json_agg(json_build_object('nom', l.nom_plat, 'quantite', l.quantite, 'total', l.total_ligne::float, 'commentaire', l.commentaire)
                              ORDER BY l.id) FILTER (WHERE l.id IS NOT NULL), '[]'::json) AS lignes
              FROM commandes c LEFT JOIN tables_restaurant t ON t.id = c.table_id LEFT JOIN lignes_commande l ON l.commande_id = c.id
              {'WHERE ' + ' AND '.join(where) if where else ''} GROUP BY c.id, t.numero ORDER BY c.created_at DESC LIMIT %s"""
    with cursor() as cur:
        cur.execute(sql, (*params, limit))
        return cur.fetchall()


@router.get("/commandes/resume")
def resume_commandes():
    """Léger, interrogé en continu par le menu latéral : badge + détection des nouvelles commandes."""
    with cursor() as cur:
        cur.execute("""SELECT count(*) FILTER (WHERE statut = 'recue')::int AS recues,
                              count(*) FILTER (WHERE statut IN ('recue','en_preparation','prete','en_route'))::int AS en_cours,
                              coalesce(max(id), 0)::int AS derniere_id FROM commandes""")
        r = cur.fetchone()
        cur.execute("SELECT numero FROM commandes ORDER BY id DESC LIMIT 1")
        last = cur.fetchone()
    return {**r, "derniere_numero": last["numero"] if last else None}


#this should be taken off as well as the whole live orders logic
@router.post("/commandes/{cid}/annuler")
def annuler_commande(cid: int, user=Depends(require_role("gerant"))):
    with cursor() as cur:
        cur.execute("SELECT set_config('app.employe_id', %s, true)", (str(user["id"]),))
        cur.execute("""UPDATE commandes SET statut = 'annulee',
                              paiement_statut = CASE WHEN paiement_statut = 'paye' THEN 'rembourse'::statut_paiement ELSE paiement_statut END
                       WHERE id = %s AND statut = 'recue' RETURNING id, numero, statut::text AS statut, paiement_statut::text AS paiement_statut""", (cid,))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT 1 FROM commandes WHERE id = %s", (cid,))
            if cur.fetchone():
                raise HTTPException(409, "Seules les commandes « reçues » peuvent être annulées")
            raise HTTPException(404, "Commande introuvable")
        return row
