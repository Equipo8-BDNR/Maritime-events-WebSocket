#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
[ -f .env ] || touch .env
[ -z "$(tail -c1 .env)" ] || echo >> .env

ensure_var() {
  grep -q "^$1=" .env || echo "$1=$(openssl rand -hex 16)" >> .env
}
for v in CASSANDRA_ADMIN_PASSWORD CASSANDRA_INGEST_PASSWORD CASSANDRA_ANALYST_PASSWORD; do
  ensure_var "$v"
done
set -a
. ./.env
set +a

NODE=ais-cassandra1
cql() { docker exec -i "$NODE" cqlsh -u "$1" -p "$2"; }

echo "==> Comprobando si el bootstrap de seguridad ya se hizo"
if echo "SELECT release_version FROM system.local;" | cql ais_admin "$CASSANDRA_ADMIN_PASSWORD" >/dev/null 2>&1; then
  echo "    ais_admin ya existe, se omite el bootstrap"
else
  echo "==> Bootstrap: replicacion de system_auth y superusuario propio"
  cql cassandra cassandra <<CQL
ALTER KEYSPACE system_auth WITH replication = {'class': 'NetworkTopologyStrategy', 'dc1': 3};
CREATE ROLE IF NOT EXISTS ais_admin WITH SUPERUSER = true AND LOGIN = true AND PASSWORD = '${CASSANDRA_ADMIN_PASSWORD}';
CQL
  for n in 1 2 3 4; do
    docker exec "ais-cassandra$n" nodetool repair -full system_auth >/dev/null
  done
  echo "==> Deshabilitando el usuario por defecto 'cassandra'"
  cql ais_admin "$CASSANDRA_ADMIN_PASSWORD" <<CQL
ALTER ROLE cassandra WITH PASSWORD = '$(openssl rand -hex 24)' AND SUPERUSER = false AND LOGIN = false;
CQL
fi

echo "==> Keyspace y roles de la aplicacion"
cql ais_admin "$CASSANDRA_ADMIN_PASSWORD" <<CQL
CREATE KEYSPACE IF NOT EXISTS ais WITH replication = {'class': 'NetworkTopologyStrategy', 'dc1': 3} AND durable_writes = true;
CREATE ROLE IF NOT EXISTS ais_ingest WITH LOGIN = true AND PASSWORD = '${CASSANDRA_INGEST_PASSWORD}';
CREATE ROLE IF NOT EXISTS ais_analyst WITH LOGIN = true AND PASSWORD = '${CASSANDRA_ANALYST_PASSWORD}';
GRANT SELECT ON KEYSPACE ais TO ais_ingest;
GRANT MODIFY ON KEYSPACE ais TO ais_ingest;
GRANT SELECT ON KEYSPACE ais TO ais_analyst;
CQL

echo "==> Permisos resultantes"
echo "LIST ALL PERMISSIONS ON KEYSPACE ais;" | cql ais_admin "$CASSANDRA_ADMIN_PASSWORD"

echo "==> Prueba de control de accesos"
cql ais_admin "$CASSANDRA_ADMIN_PASSWORD" <<CQL
CREATE TABLE IF NOT EXISTS ais.acl_test (id int PRIMARY KEY, v text);
CQL
sleep 5

if echo "INSERT INTO ais.acl_test (id, v) VALUES (1, 'ingest');" | cql ais_ingest "$CASSANDRA_INGEST_PASSWORD" >/dev/null 2>&1; then
  echo "    OK   ais_ingest SI puede escribir"
else
  echo "    FALLO ais_ingest deberia poder escribir"
fi
if echo "INSERT INTO ais.acl_test (id, v) VALUES (2, 'analyst');" | cql ais_analyst "$CASSANDRA_ANALYST_PASSWORD" >/dev/null 2>&1; then
  echo "    FALLO ais_analyst NO deberia poder escribir"
else
  echo "    OK   ais_analyst NO puede escribir (Unauthorized)"
fi
if echo "SELECT * FROM ais.acl_test;" | cql ais_analyst "$CASSANDRA_ANALYST_PASSWORD" >/dev/null 2>&1; then
  echo "    OK   ais_analyst SI puede leer"
else
  echo "    FALLO ais_analyst deberia poder leer"
fi
if echo "SELECT * FROM ais.acl_test;" | cql cassandra cassandra >/dev/null 2>&1; then
  echo "    FALLO el usuario por defecto cassandra sigue activo"
else
  echo "    OK   el usuario por defecto cassandra ya no puede entrar"
fi

echo "DROP TABLE ais.acl_test;" | cql ais_admin "$CASSANDRA_ADMIN_PASSWORD"
echo "==> Listo. Las contrasenas estan en .env (no se sube a git)."
