#!/usr/bin/env python3
"""Apply migrations/001_demo_analytics.sql + 002_stripe_billing.sql.

NOTE: requires a direct Postgres connection to the Supabase project (NOT the
localhost DB_* in the repo .env — those are legacy dev creds). Get the prod
Postgres password from Supabase Dashboard → Project Settings → Database, then
set SUPABASE_DB_HOST / SUPABASE_DB_PASSWORD before running. The fastest path is
to paste each migrations/*.sql into the Supabase SQL editor instead.

Usage:
  SUPABASE_DB_HOST=db.<ref>.supabase.co \\
  SUPABASE_DB_PASSWORD=<project_db_password> \\
  python scripts/migrate_stripe.py
"""
import os, sys, glob
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

host = os.getenv("SUPABASE_DB_HOST")
pw   = os.getenv("SUPABASE_DB_PASSWORD")
if not (host and pw):
    print("ERROR: set SUPABASE_DB_HOST and SUPABASE_DB_PASSWORD (see header).")
    print("Quickest path: paste migrations/*.sql into the Supabase SQL editor.")
    sys.exit(2)

import psycopg2
conn = psycopg2.connect(
    host=host, port=int(os.getenv("SUPABASE_DB_PORT", "5432")),
    dbname=os.getenv("SUPABASE_DB_NAME", "postgres"),
    user=os.getenv("SUPABASE_DB_USER", "postgres"),
    password=pw, sslmode="require", connect_timeout=15,
)
conn.autocommit = True

mig_dir = os.path.join(os.path.dirname(__file__), "..", "migrations")
files = sorted(glob.glob(os.path.join(mig_dir, "*.sql")))
print(f"applying {len(files)} migration(s) to {host}")
for path in files:
    sql = open(path).read()
    name = os.path.basename(path)
    print(f"  • {name}")
    with conn.cursor() as cur:
        cur.execute(sql)
print("done.")
