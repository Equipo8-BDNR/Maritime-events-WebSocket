#!/usr/bin/env python3

import argparse
import asyncio
import json
import os
import random
import time
import uuid

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import websockets
from dotenv import load_dotenv

from cassandra import ConsistencyLevel
from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster, DCAwareRoundRobinPolicy


# --------------------------------------------------
# Configuración
# --------------------------------------------------

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

AIS_URL = "wss://stream.aisstream.io/v0/stream"

SHARDS = 16

INSERT_CQL = """
INSERT INTO raw_events (
    event_day,
    event_hour,
    shard,
    event_id,
    message_type,
    mmsi,
    payload,
    received_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


# --------------------------------------------------
# Utilidades
# --------------------------------------------------

def get_mmsi(message):
    metadata = message.get("MetaData") or {}

    mmsi = metadata.get("MMSI")

    if mmsi is None:
        body = message.get("Message") or {}
        mmsi = body.get("MMSI")

    try:
        return int(mmsi) if mmsi is not None else None
    except (ValueError, TypeError):
        return None


def build_event(message):
    now = datetime.now(timezone.utc)

    # Cassandra recibirá fechas UTC sin zona horaria.
    received_at = now.replace(tzinfo=None)

    event_hour = now.replace(
        minute=0,
        second=0,
        microsecond=0,
        tzinfo=None
    )

    mmsi = get_mmsi(message)

    # Distribución determinista por MMSI.
    # Si no hay MMSI, se asigna un shard aleatorio.
    shard = mmsi % SHARDS if mmsi is not None else random.randrange(SHARDS)

    return (
        now.date(),
        event_hour,
        shard,
        uuid.uuid1(),
        message.get("MessageType", "UNKNOWN"),
        mmsi,
        json.dumps(message, separators=(",", ":"), ensure_ascii=False),
        received_at,
    )


# --------------------------------------------------
# Productor: recibe mensajes de AISStream
# --------------------------------------------------

async def producer(queue, duration, stats):

    api_key = os.getenv("AISSTREAM_API_KEY")

    if not api_key:
        raise RuntimeError("Falta AISSTREAM_API_KEY en .env")

    start = time.monotonic()
    last_report = start

    async with websockets.connect(
        AIS_URL,
        max_size=None,
        ping_interval=20,
        ping_timeout=20
    ) as ws:

        await ws.send(json.dumps({
            "APIKey": api_key,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
            "FilterMessageTypes": [
                "PositionReport",
                "ShipStaticData"
            ]
        }))

        print("Conectado a AISStream. Recibiendo mensajes...")

        while True:

            elapsed = time.monotonic() - start
            remaining = duration - elapsed

            if remaining <= 0:
                break

            try:
                raw = await asyncio.wait_for(
                    ws.recv(),
                    timeout=min(1.0, remaining)
                )
            except asyncio.TimeoutError:
                continue

            message = json.loads(raw)

            if "error" in message:
                raise RuntimeError(
                    f"Error de AISStream: {message['error']}"
                )

            # Los mensajes de control no se guardan como eventos.
            if "Message" not in message:
                stats["control"] += 1
                continue

            stats["received"] += 1

            event = build_event(message)

            # Si la cola está llena, espera en lugar de descartar.
            await queue.put(event)

            stats["enqueued"] += 1

            now = time.monotonic()

            if now - last_report >= 10:

                print(
                    f"Recibidos={stats['received']} | "
                    f"Encolados={stats['enqueued']} | "
                    f"Guardados={stats['persisted']} | "
                    f"Fallidos={stats['failed']} | "
                    f"En cola={queue.qsize()}"
                )

                last_report = now


# --------------------------------------------------
# Consumidores: escriben en Cassandra
# --------------------------------------------------

async def worker(queue, session, prepared, executor, stats):

    loop = asyncio.get_running_loop()

    while True:

        event = await queue.get()

        try:

            for attempt in range(3):

                try:

                    await loop.run_in_executor(
                        executor,
                        session.execute,
                        prepared,
                        event
                    )

                    stats["persisted"] += 1
                    break

                except Exception as error:

                    if attempt == 2:

                        stats["failed"] += 1

                        print(
                            f"Error definitivo al guardar evento: {error}"
                        )

                    else:

                        await asyncio.sleep(2 ** attempt)

        finally:
            queue.task_done()


# --------------------------------------------------
# Programa principal
# --------------------------------------------------

async def main():

    parser = argparse.ArgumentParser(
        description="Consumidor AISStream -> Cassandra"
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duración de captura en segundos"
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Número de trabajadores de Cassandra"
    )

    parser.add_argument(
        "--queue-size",
        type=int,
        default=5000,
        help="Capacidad máxima de la cola"
    )

    args = parser.parse_args()

    # Variables de Cassandra.
    hosts = os.getenv("CASSANDRA_HOSTS", "").split(",")

    hosts = [host.strip() for host in hosts if host.strip()]

    port = int(os.getenv("CASSANDRA_PORT", "9042"))

    username = os.getenv("CASSANDRA_INGEST_USER", "ais_ingest")
    password = os.getenv("CASSANDRA_INGEST_PASSWORD")

    if not hosts:
        raise RuntimeError("Falta CASSANDRA_HOSTS en .env")

    if not password:
        raise RuntimeError("Falta CASSANDRA_INGEST_PASSWORD en .env")

    # Conexión a Cassandra.
    auth_provider = PlainTextAuthProvider(
        username=username,
        password=password
    )

    cluster = Cluster(
        contact_points=hosts,
        port=port,
        auth_provider=auth_provider,
        load_balancing_policy=DCAwareRoundRobinPolicy(
            local_dc="dc1"
        )
    )

    session = cluster.connect("ais")

    prepared = session.prepare(INSERT_CQL)
    prepared.consistency_level = ConsistencyLevel.LOCAL_QUORUM

    print("Conexión con Cassandra establecida.")

    # Cola limitada.
    queue = asyncio.Queue(maxsize=args.queue_size)

    stats = Counter()

    # Executor con un número limitado de hilos.
    executor = ThreadPoolExecutor(
        max_workers=args.workers
    )

    workers = [
        asyncio.create_task(
            worker(queue, session, prepared, executor, stats)
        )
        for _ in range(args.workers)
    ]

    start = time.monotonic()

    try:

        await producer(
            queue,
            args.duration,
            stats
        )

    finally:

        print("\nRecepción finalizada. Vaciando la cola...")

        # Espera a que Cassandra procese todos los eventos pendientes.
        await queue.join()

        # Detiene los trabajadores.
        for task in workers:
            task.cancel()

        await asyncio.gather(
            *workers,
            return_exceptions=True
        )

        executor.shutdown(wait=True)

        session.shutdown()
        cluster.shutdown()

    elapsed = time.monotonic() - start

    print("\n========== RESUMEN ==========")
    print(f"Duración:       {elapsed:.1f} s")
    print(f"Recibidos:      {stats['received']}")
    print(f"Encolados:      {stats['enqueued']}")
    print(f"Guardados:      {stats['persisted']}")
    print(f"Fallidos:       {stats['failed']}")
    print(f"Control:        {stats['control']}")

    if elapsed > 0:
        print(
            f"Rendimiento:    "
            f"{stats['persisted'] / elapsed:.1f} escrituras/s"
        )


if __name__ == "__main__":
    asyncio.run(main())