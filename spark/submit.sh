#!/usr/bin/env bash
set -euo pipefail
JOB="${1:?uso: bash spark/submit.sh <archivo_del_job.py>}"
docker exec ais-spark-master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --packages com.datastax.spark:spark-cassandra-connector_2.12:3.5.1,io.delta:delta-spark_2.12:3.2.0 \
  --conf spark.jars.ivy=/tmp/ivy \
  --conf spark.driver.memory=512m \
  --conf spark.executor.memory=1g \
  --conf spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension \
  --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog \
  --conf spark.cassandra.connection.host=cassandra1 \
  "/opt/jobs/${JOB}"
