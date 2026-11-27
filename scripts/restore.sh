#!/usr/bin/env bash
# Restaure une sauvegarde dans une base PostgreSQL.
#
# Usage :  ./scripts/restore.sh backups/yummy_20261125_020000.sql.gz [base_cible]
#   base_cible : par défaut la base du .env (POSTGRES_DB). Elle est créée si elle n'existe pas.
#   Si la base cible contient déjà des tables, elles seront REMPLACÉES : une confirmation est demandée
#   (CONFIRM=yes pour la passer, par exemple dans un script).
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
trap 'echo "[restore] ERREUR à la ligne $LINENO" >&2' ERR

file="${1:?Usage : $0 <fichier.sql.gz> [base_cible]}"
target="${2:-$POSTGRES_DB}"
[[ -f "$file" ]] || { echo "[restore] Fichier introuvable : $file" >&2; exit 1; }

exists="$(pg psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$target'")"
if [[ "$exists" != "1" ]]; then
  echo "[restore] Création de la base « $target »"
  pg createdb -U "$POSTGRES_USER" "$target"
fi

tables="$(pg psql -U "$POSTGRES_USER" -d "$target" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")"
if [[ "$tables" -gt 0 && "${CONFIRM:-}" != "yes" ]]; then
  echo "[restore] La base « $target » contient déjà $tables tables : elles vont être REMPLACÉES."
  read -r -p "Tapez « oui » pour continuer : " answer
  [[ "$answer" == "oui" ]] || { echo "[restore] Annulé."; exit 1; }
fi

echo "[restore] $file -> base « $target »"
gunzip -c "$file" | pg psql -U "$POSTGRES_USER" -d "$target" -v ON_ERROR_STOP=1 -q -o /dev/null
echo "[restore] OK"
