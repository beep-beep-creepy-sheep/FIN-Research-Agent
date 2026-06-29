# Backup And Restore

Back up the database and configured storage directories before migrations or release upgrades.

## SQLite

Stop API/worker, then copy the database and data directory:

```bash
cp data/finresearch.sqlite data/finresearch.sqlite.backup
tar -czf finresearch-data-backup.tgz data
```

Restore by stopping services and replacing the database/data directory from the backup.

## PostgreSQL

```bash
pg_dump --format=custom --file=finresearch.backup '<DATABASE_URL>'
pg_restore --clean --if-exists --dbname='<DATABASE_URL>' finresearch.backup
```

Do not store backups containing private reports or cookies in the repository.

