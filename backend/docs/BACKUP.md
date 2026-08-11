# Database Operations: Backup, Restore, Migrations, Retention (W5)

## Backups

**Logical backup (mongodump)** — simplest for a single-node deployment:

```bash
# Full backup (authenticated). Store OFF the DB host, encrypted, with retention.
mongodump --uri "mongodb://$MONGO_ROOT_USER:$MONGO_ROOT_PASSWORD@localhost:27017/?authSource=admin" \
          --archive="backup-$(date +%F-%H%M).gz" --gzip
```

Schedule it (nightly cron / systemd timer / a Cowork scheduled task):

```cron
0 2 * * *  mongodump --uri "$MONGODB_URI" --archive=/backups/ai_tutor-$(date +\%F).gz --gzip
```

Guidance:
- **3-2-1**: 3 copies, 2 media, 1 offsite. Push archives to object storage (S3/GCS) with lifecycle expiry (e.g. keep 30 dailies + 12 monthlies).
- **Encrypt at rest** (server-side encryption or `gpg`), since dumps contain hashed passwords and user data.
- **Restrict scope** if needed: `--db ai_tutor`.

## Restore

```bash
mongorestore --uri "mongodb://$MONGO_ROOT_USER:$MONGO_ROOT_PASSWORD@localhost:27017/?authSource=admin" \
             --archive="backup-2026-08-04-0200.gz" --gzip --drop
```

`--drop` replaces existing collections. **Test restores regularly** into a scratch
database — an untested backup is not a backup.

## Point-in-time recovery (PITR)

`mongodump` gives snapshot-granularity recovery. For tighter RPO:
- Run MongoDB as a **replica set** and back up the **oplog**, or
- Use **MongoDB Atlas** continuous/cloud backups (managed PITR), or
- Use filesystem/volume snapshots on a quiesced/`fsync`-locked node.

Pick a target **RPO/RTO** and document it; nightly logical dumps imply up-to-24h RPO.

## Deploy sequence

1. Apply schema/index changes as an explicit step (fails loudly, blocks a bad rollout):
   ```bash
   python -m scripts.migrate_indexes
   ```
2. Start the API with `AUTO_ENSURE_INDEXES=0` (the migration owns indexes now):
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
   ```
3. `/healthz` returns `200` with `{"mongo": true}` once ready.

## Telemetry retention

`interactions`, `llm_calls`, and `rl_transitions` are append-heavy and store float
epochs (a Mongo TTL index is a no-op on non-date fields), so prune them on a
schedule:

```bash
python -m scripts.telemetry_maintenance --dry-run   # preview
python -m scripts.telemetry_maintenance             # delete beyond retention
```

Defaults: interactions 90d, llm_calls 30d, rl_transitions 180d — override via
`RETAIN_INTERACTIONS_DAYS` / `RETAIN_LLM_CALLS_DAYS` / `RETAIN_RL_TRANSITIONS_DAYS`
(0 disables a collection). **Export to a warehouse before pruning** if you need
long-term analytics.

## Production Mongo hardening (M-9)

The prod override (`docker-compose.prod.yml`) enables `--auth`, injects root
credentials from the environment, and stops publishing the DB/cache ports. Keep
Mongo and Redis on the internal compose network; expose only the API behind TLS.
