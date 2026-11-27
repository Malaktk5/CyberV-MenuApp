#!/usr/bin/env bash
# Test de restauration de bout en bout : sauvegarde -> restauration dans une base VIDE -> comparaison du nombre de lignes
# de chaque table. Le résultat est écrit dans docs/restore-test.log (à commiter comme preuve).
#
# Usage :  ./scripts/restore_test.sh
# À lancer quand la base est calme (pas de commandes en cours), sinon les comptes peuvent différer légèrement.
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

LOG="${LOG:-docs/restore-test.log}"
TEST_DB="yummy_restore_test"
mkdir -p "$(dirname "$LOG")"

counts() {   # counts <base> : une ligne « table|nombre » par table
  local db="$1" t
  for t in $(pg psql -U "$POSTGRES_USER" -d "$db" -tAc "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1"); do
    printf '%s|%s\n' "$t" "$(pg psql -U "$POSTGRES_USER" -d "$db" -tAc "SELECT count(*) FROM \"$t\"")"
  done
}

{
  echo "=== Test de restauration — $(date '+%F %T') ==="
  echo "Base source : $POSTGRES_DB  |  base de test (vide) : $TEST_DB"
  echo
  ./scripts/backup.sh
  file="$(ls -1t "$BACKUP_DIR"/yummy_*.sql.gz | head -1)"
  echo "Sauvegarde utilisée : $file"

  pg dropdb -U "$POSTGRES_USER" --if-exists "$TEST_DB"
  pg createdb -U "$POSTGRES_USER" "$TEST_DB"
  CONFIRM=yes ./scripts/restore.sh "$file" "$TEST_DB"

  src="$(counts "$POSTGRES_DB")"; res="$(counts "$TEST_DB")"
  echo
  printf '%-24s %12s %12s\n' "TABLE" "SOURCE" "RESTAURÉE"
  join -t'|' <(echo "$src") <(echo "$res") | awk -F'|' '{ printf "%-24s %12s %12s  %s\n", $1, $2, $3, ($2==$3 ? "OK" : "DIFFÉRENT") }'
  echo
  pg dropdb -U "$POSTGRES_USER" "$TEST_DB"
  if [[ "$src" == "$res" ]]; then
    echo "RÉSULTAT : OK — toutes les tables ont le même nombre de lignes après restauration."
  else
    echo "RÉSULTAT : ÉCHEC — des différences ont été trouvées." ; exit 1
  fi
} 2>&1 | tee "$LOG"
