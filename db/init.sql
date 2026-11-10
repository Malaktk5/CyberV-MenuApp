BEGIN;

-- ===== TYPES =====
CREATE TYPE role_employe    AS ENUM ('serveur', 'cuisinier', 'caissier', 'livreur', 'gerant');
CREATE TYPE mode_commande   AS ENUM ('sur_place', 'a_emporter', 'livraison');
CREATE TYPE statut_commande AS ENUM ('recue', 'en_preparation', 'prete', 'servie', 'en_route', 'livree', 'echec', 'annulee', 'remboursee');
CREATE TYPE mode_paiement   AS ENUM ('especes', 'en_ligne');
CREATE TYPE statut_paiement AS ENUM ('en_attente', 'paye', 'rembourse');

-- ===== TABLES =====
CREATE TABLE employes (
    id                BIGSERIAL PRIMARY KEY,
    nom               VARCHAR(100) NOT NULL,
    prenom            VARCHAR(100) NOT NULL,
    email             VARCHAR(255) NOT NULL UNIQUE,
    telephone         VARCHAR(30),
    mot_de_passe_hash TEXT NOT NULL,
    role              role_employe NOT NULL,
    actif             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE categories (
    id    BIGSERIAL PRIMARY KEY,
    nom   VARCHAR(100) NOT NULL UNIQUE,
    ordre INT NOT NULL DEFAULT 0
);

CREATE TABLE plats (
    id                BIGSERIAL PRIMARY KEY,
    categorie_id      BIGINT NOT NULL REFERENCES categories(id),
    nom               VARCHAR(150) NOT NULL,
    description       TEXT,
    prix              NUMERIC(10,2) NOT NULL CHECK (prix >= 0),
    photo_url         TEXT,
    temps_preparation INT NOT NULL DEFAULT 10 CHECK (temps_preparation >= 0),
    disponible        BOOLEAN NOT NULL DEFAULT TRUE,
    archive           BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_plats_categorie ON plats(categorie_id);

CREATE TABLE options_plat (
    id      BIGSERIAL PRIMARY KEY,
    plat_id BIGINT NOT NULL REFERENCES plats(id),
    groupe  VARCHAR(50),
    nom     VARCHAR(100) NOT NULL,
    prix    NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (prix >= 0),
    actif   BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (plat_id, nom)
);

CREATE TABLE tables_restaurant (
    id       BIGSERIAL PRIMARY KEY,
    numero   INT NOT NULL UNIQUE,
    capacite INT NOT NULL DEFAULT 2 CHECK (capacite > 0),
    qr_token UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    active   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE SEQUENCE seq_commande;

CREATE TABLE commandes (
    id                 BIGSERIAL PRIMARY KEY,
    numero             VARCHAR(20) NOT NULL UNIQUE
                       DEFAULT ('CMD-' || lpad(nextval('seq_commande')::text, 6, '0')),
    suivi_token        UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    mode               mode_commande NOT NULL,
    statut             statut_commande NOT NULL DEFAULT 'recue',
    table_id           BIGINT REFERENCES tables_restaurant(id),
    serveur_id         BIGINT REFERENCES employes(id),
    livreur_id         BIGINT REFERENCES employes(id),

    client_nom         VARCHAR(100),
    client_telephone   VARCHAR(30),
    adresse_livraison  TEXT,
    motif_echec        TEXT,
    note               TEXT,

    paiement_mode      mode_paiement NOT NULL DEFAULT 'especes',
    paiement_statut    statut_paiement NOT NULL DEFAULT 'en_attente',

    sous_total         NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (sous_total >= 0),
    frais_livraison    NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (frais_livraison >= 0),
    total              NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (total >= 0),

    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    prise_en_charge_at TIMESTAMPTZ,
    prete_at           TIMESTAMPTZ,
    terminee_at        TIMESTAMPTZ,

    CONSTRAINT chk_sur_place CHECK (mode <> 'sur_place' OR table_id IS NOT NULL),
    CONSTRAINT chk_livraison CHECK (mode <> 'livraison' OR (adresse_livraison IS NOT NULL AND client_telephone IS NOT NULL))
);
CREATE INDEX idx_commandes_statut  ON commandes(statut);
CREATE INDEX idx_commandes_created ON commandes(created_at);

CREATE TABLE lignes_commande (
    id            BIGSERIAL PRIMARY KEY,
    commande_id   BIGINT NOT NULL REFERENCES commandes(id) ON DELETE CASCADE,
    plat_id       BIGINT NOT NULL REFERENCES plats(id),
    nom_plat      VARCHAR(150) NOT NULL,
    prix_unitaire NUMERIC(10,2) NOT NULL CHECK (prix_unitaire >= 0),
    quantite      INT NOT NULL CHECK (quantite > 0),
    options       JSONB NOT NULL DEFAULT '[]',
    total_ligne   NUMERIC(10,2) NOT NULL CHECK (total_ligne >= 0),
    commentaire   TEXT
);
CREATE INDEX idx_lignes_commande ON lignes_commande(commande_id);

CREATE TABLE historique_statuts (
    id             BIGSERIAL PRIMARY KEY,
    commande_id    BIGINT NOT NULL REFERENCES commandes(id) ON DELETE CASCADE,
    ancien_statut  statut_commande,
    nouveau_statut statut_commande NOT NULL,
    employe_id     BIGINT REFERENCES employes(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_hist_commande ON historique_statuts(commande_id);

-- ===== RÈGLES (2 triggers) =====

-- 1) Annulation seulement depuis "recue", horodatages, historique
CREATE OR REPLACE FUNCTION fn_commande_avant_update() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();

    IF NEW.statut IS DISTINCT FROM OLD.statut THEN
        IF NEW.statut IN ('annulee', 'remboursee')
           AND OLD.statut NOT IN ('recue', 'annulee', 'remboursee') THEN
            RAISE EXCEPTION 'Annulation impossible : la commande est déjà au statut %', OLD.statut;
        END IF;

        IF NEW.statut = 'en_preparation' THEN NEW.prise_en_charge_at := now(); END IF;
        IF NEW.statut = 'prete'          THEN NEW.prete_at := now(); END IF;
        IF NEW.statut IN ('servie', 'livree', 'echec', 'annulee', 'remboursee') THEN
            NEW.terminee_at := now();
        END IF;

        INSERT INTO historique_statuts (commande_id, ancien_statut, nouveau_statut, employe_id)
        VALUES (NEW.id, OLD.statut, NEW.statut,
                NULLIF(current_setting('app.employe_id', true), '')::BIGINT);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_commande_avant_update
BEFORE UPDATE ON commandes
FOR EACH ROW EXECUTE FUNCTION fn_commande_avant_update();

-- 2) Lignes : plus de modification après "recue", et pas de plat indisponible
CREATE OR REPLACE FUNCTION fn_lignes_regles() RETURNS trigger AS $$
DECLARE
    v_statut statut_commande;
    v_ok     BOOLEAN;
BEGIN
    SELECT statut INTO v_statut FROM commandes
    WHERE id = COALESCE(NEW.commande_id, OLD.commande_id);

    IF v_statut <> 'recue' THEN
        RAISE EXCEPTION 'Modification impossible : la commande est au statut %', v_statut;
    END IF;

    IF TG_OP = 'INSERT' THEN
        SELECT (disponible AND NOT archive) INTO v_ok FROM plats WHERE id = NEW.plat_id;
        IF NOT COALESCE(v_ok, FALSE) THEN
            RAISE EXCEPTION 'Le plat % est indisponible', NEW.plat_id;
        END IF;
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_lignes_regles
BEFORE INSERT OR UPDATE OR DELETE ON lignes_commande
FOR EACH ROW EXECUTE FUNCTION fn_lignes_regles();

-- ===== DONNÉES DE DÉPART (pas d'admin ici : créé par Python depuis .env) =====
INSERT INTO categories (nom, ordre) VALUES
    ('Entrées', 1), ('Plats', 2), ('Desserts', 3), ('Boissons', 4);

INSERT INTO tables_restaurant (numero, capacite) VALUES (1, 2), (2, 4), (3, 4), (4, 6);

INSERT INTO plats (categorie_id, nom, description, prix, temps_preparation)
SELECT c.id, d.nom, d.descr, d.prix, d.tps FROM (VALUES
  ('Entrées',  'Salade César',     'Poulet, parmesan, croûtons',   650,  8),
  ('Entrées',  'Soupe du jour',    'Selon l''arrivage',            400,  5),
  ('Plats',    'Burger maison',    'Boeuf, cheddar, frites',      1200, 15),
  ('Plats',    'Pizza Margherita', 'Tomate, mozzarella, basilic',  900, 12),
  ('Desserts', 'Tiramisu',         'Maison',                       450,  3),
  ('Boissons', 'Citronnade',       'Fraîche',                      250,  2),
  ('Boissons', 'Café',             'Expresso',                     150,  2)
) AS d(cat, nom, descr, prix, tps)
JOIN categories c ON c.nom = d.cat;

INSERT INTO options_plat (plat_id, groupe, nom, prix)
SELECT id, 'Cuisson', o.nom, 0
FROM plats CROSS JOIN (VALUES ('Saignant'), ('À point'), ('Bien cuit')) AS o(nom)
WHERE plats.nom = 'Burger maison';

INSERT INTO options_plat (plat_id, groupe, nom, prix)
SELECT id, NULL, 'Fromage en plus', 100 FROM plats WHERE nom = 'Burger maison';

COMMIT;
