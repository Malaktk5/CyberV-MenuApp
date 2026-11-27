#!/usr/bin/env bash
# Fonctions communes à backup.sh, restore.sh et restore_test.sh (ce fichier est "sourcé", on ne le lance pas).

cd "$(dirname "${BASH_SOURCE[0]}")/.."   # on se place à la racine du projet

# Variables du fichier .env (POSTGRES_USER, POSTGRES_DB, ...). Si le .env n'existe pas, on utilise l'environnement.
if [[ -f .env ]]; then set -a; . ./.env; set +a; fi
: "${POSTGRES_USER:?POSTGRES_USER manquant (fichier .env)}"
: "${POSTGRES_DB:?POSTGRES_DB manquant (fichier .env)}"

USE_DOCKER="${USE_DOCKER:-1}"                    # 1 = commandes exécutées dans le conteneur PostgreSQL ; 0 = psql/pg_dump installés sur la machine
DB_CONTAINER="${DB_CONTAINER:-yummy_postgres}"   # nom du conteneur (container_name du docker-compose.yml)
PGHOST="${PGHOST:-localhost}"; PGPORT="${PGPORT:-5433}"   # utilisés seulement si USE_DOCKER=0
BACKUP_DIR="${BACKUP_DIR:-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# pg <commande> [arguments...] : lance pg_dump / psql / createdb ... ; l'entrée standard est transmise.
pg() {
  if [[ "$USE_DOCKER" == "1" ]]; then
    docker exec -i "$DB_CONTAINER" "$@"
  else
    PGPASSWORD="${POSTGRES_PASSWORD:-}" "$1" -h "$PGHOST" -p "$PGPORT" "${@:2}"
  fi
}
