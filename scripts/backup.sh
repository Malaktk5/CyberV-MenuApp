#!/usr/bin/env bash
# Sauvegarde de la base PostgreSQL dans backups/yummy_AAAAMMJJ_HHMMSS.sql.gz
# et suppression des sauvegardes de plus de 7 jours (RETENTION_DAYS).
#
# Usage manuel :  ./scripts/backup.sh
# Cron, tous les jours à 02:00 (crontab -e) :
#   0 2 * * * cd /chemin/vers/CyberV-MenuApp && ./scripts/backup.sh >> backups/backup.log 2>&1
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

mkdir -p "$BACKUP_DIR"
file="$BACKUP_DIR/yummy_$(date +%Y%m%d_%H%M%S).sql.gz"
tmp="$file.part"
trap 'echo "[backup] ERREUR à la ligne $LINENO" >&2; rm -f "$tmp"' ERR

echo "[backup] $(date '+%F %T') pg_dump de « $POSTGRES_DB » -> $file"
pg pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner | gzip > "$tmp"
mv "$tmp" "$file"          # le fichier n'apparaît sous son vrai nom que si la sauvegarde est complète

find "$BACKUP_DIR" -maxdepth 1 -name 'yummy_*.sql.gz' -mtime +"$RETENTION_DAYS" -print -delete \
  | sed "s|^|[backup] supprimé (plus de $RETENTION_DAYS jours) : |"
echo "[backup] OK ($(du -h "$file" | cut -f1))"
