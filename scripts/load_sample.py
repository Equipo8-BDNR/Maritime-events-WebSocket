import json
import os
import sys
import time
from datetime import datetime, timedelta

from cassandra import ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
from cassandra.concurrent import execute_concurrent_with_args
from cassandra.policies import WhiteListRoundRobinPolicy
from dotenv import load_dotenv

load_dotenv()

EPOCH = datetime(1970, 1, 1)
LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else None

POS_COLS = ("event_time, message_id, ship_name, latitude, longitude, sog, cog, true_heading, "
            "rate_of_turn, nav_status, position_accuracy, raim, report_second")
POS_MARKS = ", ".join(["?"] * 13)


def parse_time(s):
    s = s.replace(" +0000 UTC", "")
    date, clock = s.split(" ")
    hms, _, frac = clock.partition(".")
    frac9 = (frac + "000000000")[:9]
    dt = datetime.strptime(f"{date} {hms}.{frac9[:6]}", "%Y-%m-%d %H:%M:%S.%f")
    sub_ms = int(frac9[3:])
    return dt, sub_ms


def micros(dt):
    return (dt - EPOCH) // timedelta(microseconds=1)


def position_values(m):
    p = m["Message"]["PositionReport"]
    t, sub_ms = parse_time(m["MetaData"]["time_utc"])
    vals = (t, p["MessageID"], m["MetaData"]["ShipName"].strip(), p["Latitude"], p["Longitude"],
            p["Sog"], p["Cog"], p["TrueHeading"], p["RateOfTurn"], p["NavigationalStatus"],
            p["PositionAccuracy"], p["Raim"], p["Timestamp"])
    return t, sub_ms, vals


def static_values(m):
    s = m["Message"]["ShipStaticData"]
    t, _ = parse_time(m["MetaData"]["time_utc"])
    d, e = s["Dimension"], s["Eta"]
    vals = (m["MetaData"]["MMSI"], t, s["Name"].strip(), s["CallSign"].strip(), s["ImoNumber"], s["Type"],
            d["A"], d["B"], d["C"], d["D"], s["MaximumStaticDraught"], s["Destination"].strip(),
            e["Month"], e["Day"], e["Hour"], e["Minute"], s["FixType"], s["AisVersion"])
    return t, vals


def main():
    password = os.environ["CASSANDRA_INGEST_PASSWORD"]
    profile = ExecutionProfile(
        load_balancing_policy=WhiteListRoundRobinPolicy(["127.0.0.1"]),
        consistency_level=ConsistencyLevel.QUORUM,
        request_timeout=30,
    )
    cluster = Cluster(
        ["127.0.0.1"], port=9042,
        auth_provider=PlainTextAuthProvider("ais_ingest", password),
        execution_profiles={EXEC_PROFILE_DEFAULT: profile},
    )
    session = cluster.connect("ais")

    st_latest = session.prepare(
        f"INSERT INTO vessel_latest (mmsi, {POS_COLS}) VALUES (?, {POS_MARKS}) USING TIMESTAMP ?")
    st_hist = session.prepare(
        "INSERT INTO position_by_vessel_day (mmsi, day, event_time, event_nanos, message_id, ship_name, latitude, "
        "longitude, sog, cog, true_heading, rate_of_turn, nav_status, position_accuracy, raim, report_second) "
        "VALUES (" + ", ".join(["?"] * 16) + ")")
    st_static = session.prepare(
        "INSERT INTO vessel_static (mmsi, updated_at, name, call_sign, imo_number, ship_type, dim_a, dim_b, "
        "dim_c, dim_d, max_draught, destination, eta_month, eta_day, eta_hour, eta_minute, fix_type, ais_version) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) USING TIMESTAMP ?")

    latest, hist, static = [], [], []
    with open("data/sample.jsonl", encoding="utf-8") as f:
        for line in f:
            m = json.loads(line)
            kind = m.get("MessageType")
            if kind == "PositionReport":
                t, sub_ms, vals = position_values(m)
                mmsi = m["MetaData"]["MMSI"]
                latest.append((mmsi, *vals, micros(t)))
                hist.append((mmsi, t.date(), vals[0], sub_ms, *vals[1:]))
            elif kind == "ShipStaticData":
                t, vals = static_values(m)
                static.append((*vals, micros(t)))
            if LIMIT and len(latest) + len(static) >= LIMIT:
                break

    total_ok = total_fail = 0
    start = time.time()
    for name, stmt, args in (("vessel_latest", st_latest, latest),
                             ("position_by_vessel_day", st_hist, hist),
                             ("vessel_static", st_static, static)):
        t0 = time.time()
        results = execute_concurrent_with_args(session, stmt, args, concurrency=128, raise_on_first_error=False)
        fail = [r[1] for r in results if not r[0]]
        ok = len(results) - len(fail)
        total_ok += ok
        total_fail += len(fail)
        dt = time.time() - t0
        print(f"{name}: {ok} ok, {len(fail)} fallos, {ok / dt:.0f} escrituras/s")
        if fail:
            print("  primer error:", fail[0])
    print(f"Total: {total_ok} escrituras en {time.time() - start:.1f}s, {total_fail} fallos")

    n = session.execute("SELECT count(*) FROM vessel_latest").one()[0]
    print(f"vessel_latest tiene {n} barcos distintos")
    row = session.execute("SELECT mmsi, event_time, latitude, longitude, sog FROM vessel_latest LIMIT 1").one()
    print("ejemplo:", row)
    cluster.shutdown()


main()
