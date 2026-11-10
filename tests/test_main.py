import sys
import os
import psycopg2
import pytest
from fastapi.testclient import TestClient

# Correction du chemin d'importation Python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

client = TestClient(app)

def get_db_url():
    return os.getenv("DATABASE_URL", "postgresql://yummy_user:yummy_password@db:5432/yummy_db")

# 1. TEST API HEALTHCHECK
def test_health_check():
    """Vérifie la route /health et le statut de connexion PostgreSQL."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "OK", "database": "connected"}

# 2. TESTS DB POSTGRESQL
def test_db_tables_exist():
    """Vérifie la présence des 8 tables requises."""
    conn = psycopg2.connect(get_db_url())
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    expected = ["employes", "categories", "plats", "options_plat", "tables_restaurant", "commandes", "lignes_commande", "historique_statuts"]
    for table in expected:
        assert table in tables

def test_db_roles_enum():
    """Vérifie les 5 rôles métier de l'ENUM role_employe."""
    conn = psycopg2.connect(get_db_url())
    cursor = conn.cursor()
    cursor.execute("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'role_employe'::regtype;")
    roles = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    for expected_role in ['serveur', 'cuisinier', 'caissier', 'livreur', 'gerant']:
        assert expected_role in roles

def test_db_initial_plats_count():
    """Vérifie le chargement des plats de seed."""
    conn = psycopg2.connect(get_db_url())
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM plats;")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    assert count >= 7

def test_db_insert_plat_rollback():
    """Test de transaction avec insertion et rollback."""
    conn = psycopg2.connect(get_db_url())
    cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (nom) VALUES (%s) RETURNING id;", ("Catégorie Test",))
    cat_id = cursor.fetchone()[0]
    assert cat_id is not None
    conn.rollback()

    cursor.execute("SELECT COUNT(*) FROM categories WHERE nom = %s;", ("Catégorie Test",))
    assert cursor.fetchone()[0] == 0
    cursor.close()
    conn.close()
