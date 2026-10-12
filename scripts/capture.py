import asyncio
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import websockets
from dotenv import load_dotenv

load_dotenv()

URL = "wss://stream.aisstream.io/v0/stream"
DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 600
OUT = Path("data/sample.jsonl")


async def main():
    key = os.environ.get("AISSTREAM_API_KEY")
    if not key:
        sys.exit("Falta AISSTREAM_API_KEY en .env")

    OUT.parent.mkdir(exist_ok=True)
    counts = Counter()
    start = time.time()
    last_report = start

    async with websockets.connect(URL, max_size=None) as ws:
        await ws.send(json.dumps({
            "APIKey": key,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        }))
        with OUT.open("w", encoding="utf-8") as f:
            async for raw in ws:
                text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                msg = json.loads(text)
                if "error" in msg:
                    sys.exit(f"Error del servidor: {msg['error']}")
                f.write(text.strip() + "\n")
                counts[msg.get("MessageType", "?")] += 1

                now = time.time()
                if now - last_report >= 30:
                    total = sum(counts.values())
                    print(f"{int(now - start):4d}s  total={total}  {total / (now - start):.1f} msg/s  {dict(counts)}", flush=True)
                    last_report = now
                if now - start >= DURATION:
                    break

    total = sum(counts.values())
    elapsed = time.time() - start
    print(f"\nListo: {total} mensajes en {elapsed:.0f}s = {total / elapsed:.1f} msg/s")
    print(dict(counts))


asyncio.run(main())
