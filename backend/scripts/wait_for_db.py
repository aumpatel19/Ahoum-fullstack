"""Block until Postgres accepts connections, or give up loudly.

Compose already gates the backend on the database's healthcheck; this exists so
the container also behaves when it is started on its own, and so the logs say
what it is waiting for instead of crash-looping.
"""

import os
import sys
import time

import psycopg

DSN = os.environ["DATABASE_URL"]
DEADLINE = time.monotonic() + 60

while True:
    try:
        with psycopg.connect(DSN, connect_timeout=3):
            print("Database is accepting connections.")
            break
    except psycopg.OperationalError as exc:
        if time.monotonic() > DEADLINE:
            print(f"Database still unreachable after 60s: {exc}", file=sys.stderr)
            sys.exit(1)
        print("Waiting for the database...")
        time.sleep(2)
