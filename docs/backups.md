# Sauvegarde et restauration de la base PostgreSQL

Les scripts se trouvent dans `scripts/`. Ils fonctionnent avec la stack Docker (conteneur `yummy_postgres`) et lisent
`POSTGRES_USER` et `POSTGRES_DB` dans le fichier `.env`.

## Sauvegarder

```bash
./scripts/backup.sh
```

Crée `backups/yummy_AAAAMMJJ_HHMMSS.sql.gz` (dump complet, compressé) et supprime les sauvegardes de plus de 7 jours.
Le dossier `backups/` est ignoré par Git : les sauvegardes ne doivent jamais être commitées (elles contiennent des données clients).

## Sauvegarde automatique à 02:00

Ouvrir la table cron avec `crontab -e` et ajouter la ligne (en adaptant le chemin) :

```
0 2 * * * cd /chemin/vers/CyberV-MenuApp && ./scripts/backup.sh >> backups/backup.log 2>&1
```

Vérifier ensuite avec `crontab -l`. Chaque exécution écrit une ligne dans `backups/backup.log`.

## Restaurer

```bash
./scripts/restore.sh backups/yummy_20261125_020000.sql.gz            # vers la base du .env
./scripts/restore.sh backups/yummy_20261125_020000.sql.gz ma_base    # vers une autre base (créée si besoin)
```

Si la base cible contient déjà des tables, elles sont **remplacées** : le script demande de taper « oui »
(ou `CONFIRM=yes` dans un script). En cas de vrai incident : arrêter l'application, restaurer, puis la relancer.

## Test de restauration

```bash
./scripts/restore_test.sh
```

Fait une sauvegarde, la restaure dans une base **vide** temporaire, compare le nombre de lignes de chaque table
avec la base d'origine, puis supprime la base temporaire. Le résultat est enregistré dans `docs/restore-test.log`.

## Variables optionnelles

- `USE_DOCKER=0` : utiliser `pg_dump` / `psql` installés sur la machine (avec `PGHOST`, `PGPORT` et `POSTGRES_PASSWORD`) au lieu du conteneur.
- `DB_CONTAINER` : nom du conteneur PostgreSQL (par défaut `yummy_postgres`).
- `BACKUP_DIR` : dossier des sauvegardes (par défaut `backups`).
- `RETENTION_DAYS` : durée de conservation en jours (par défaut `7`).
