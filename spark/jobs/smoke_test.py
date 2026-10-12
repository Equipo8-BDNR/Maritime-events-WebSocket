import os

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = (
    SparkSession.builder.appName("smoke_test")
    .config("spark.cassandra.auth.username", "ais_analyst")
    .config("spark.cassandra.auth.password", os.environ["CASSANDRA_ANALYST_PASSWORD"])
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")


def read_table(name):
    return (
        spark.read.format("org.apache.spark.sql.cassandra")
        .options(keyspace="ais", table=name)
        .load()
    )


latest = read_table("vessel_latest")
print("vessel_latest filas:", latest.count())
latest.select("mmsi", "ship_name", "latitude", "longitude", "sog", "event_time").show(5, truncate=False)

hist = read_table("position_by_vessel_day")
n_hist = hist.count()
print("position_by_vessel_day filas:", n_hist)

path = "/lake/bronze/position_by_vessel_day"
hist.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(path)
back = spark.read.format("delta").load(path)
n_back = back.count()
print("filas leidas de Delta:", n_back)

back.groupBy("nav_status").count().orderBy(F.desc("count")).show(5)

print("SMOKE_TEST_OK" if n_back == n_hist and n_hist > 0 else "SMOKE_TEST_FALLO")
spark.stop()
