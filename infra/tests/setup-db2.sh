#!/bin/bash
set -e

INSTANCE_DIR="/database/db2inst1"
DBNAME="${DBNAME:-testdb}"
CONFIG_DIR="/database/config"
SQL1="$CONFIG_DIR/init_job_mgmt.sql"
SQL2="$CONFIG_DIR/init_public.sql"

log() { echo "[setup-db2] $1"; }

if [ ! -d "$INSTANCE_DIR" ]; then
  log "Creating Db2 instance"
  db2icrt -u db2fenc1 db2inst1
fi

. ~db2inst1/sqllib/db2profile
db2start
sleep 5

if ! db2 list db directory | grep -iq "$DBNAME"; then
  log "Creating database '$DBNAME'"
  db2 create database "$DBNAME"
else
  log "Database '$DBNAME' already exists"
fi

log "Running init_job_mgmt.sql..."
db2 connect to "$DBNAME"
db2 -tvf "$SQL1"

log "Running init_public.sql..."
db2 -tvf "$SQL2"

log "✅ Setup complete. Sleeping forever..."
tail -f /dev/null