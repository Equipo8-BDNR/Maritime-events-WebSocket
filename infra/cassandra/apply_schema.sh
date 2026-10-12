#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a
. ./.env
set +a
docker exec -i ais-cassandra1 cqlsh -u ais_admin -p "$CASSANDRA_ADMIN_PASSWORD" < infra/cassandra/schema.cql
echo "Esquema aplicado."
echo "DESCRIBE TABLES;" | docker exec -i ais-cassandra1 cqlsh -u ais_admin -p "$CASSANDRA_ADMIN_PASSWORD" -k ais
