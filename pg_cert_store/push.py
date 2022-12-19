#!/usr/bin/env python3

import argparse
import sys
from datetime import datetime, timezone
from io import TextIOWrapper

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor

from .utils import get_cert_expiry, read_config

TABLES = {
    "certs": """CREATE TABLE {schema}.{name} (
        id SERIAL UNIQUE PRIMARY KEY,
        name VARCHAR(255) NOT NULL UNIQUE,
        public_key TEXT NOT NULL,
        private_key TEXT NOT NULL,
        expires TIMESTAMPTZ NOT NULL,
        updated TIMESTAMPTZ DEFAULT NOW()
    );"""
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Push certs to PGSQL')
    parser.add_argument('-c', '--config', type=argparse.FileType('r'), default='/etc/pg-sync-cert/config.conf', help='Path to config file')
    parser.add_argument('-n', '--name', required=True, help='Name of certificate')
    parser.add_argument('-p', '--public-key', type=argparse.FileType('r'), required=True, help='Path to public key')
    parser.add_argument('-k', '--private-key', type=argparse.FileType('r'), required=True, help='Path to private key')
    return parser.parse_args()


def create_schema(conn: psycopg2.extensions.connection, schema: str):
    with conn.cursor() as cur:
        # Check if schema exists separately, in case it is managed externally
        cur.execute("SELECT 1 FROM pg_namespace WHERE nspname=%s", (schema,))
        if not cur.fetchone():
            print(f'Creating schema "{schema}"', file=sys.stderr)
            cur.execute(f"CREATE SCHEMA {schema}")
    conn.commit()


def create_tables(conn: psycopg2.extensions.connection, schema: str):
    q_exists = "SELECT to_regclass(%s)"
    missing = []
    for name in TABLES.keys():
        with conn.cursor() as cur:
            cur.execute(q_exists, (f"{schema}.{name}", ))
            if cur.fetchone() == (None, ):
                missing.append(name)

    if missing:
        print(f'Missing {len(missing)} tables', file=sys.stderr)
    for name in missing:
        print(f'Creating "{name}" table', file=sys.stderr)
        with conn.cursor() as cur:
            cur.execute(TABLES[name].format(schema=schema, name=name))
    conn.commit()


def update_cert(conn: psycopg2.extensions.connection, schema: str, name: str, public: TextIOWrapper, private: TextIOWrapper):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT id, public_key, private_key FROM {schema}.certs WHERE name=%s", (name,))
        res = cur.fetchone()
    public_data = public.read()
    public.close()
    private_data = private.read()
    private.close()
    expires = get_cert_expiry(public_data)
    if res and (res['public_key'] != public_data or res['private_key'] != private_data):
        with conn.cursor() as cur:
            q = (f"UPDATE {schema}.certs SET "
                 "public_key=%s, private_key=%s, expires=%s, updated=%s "
                 "WHERE id=%s")
            q_args = (public_data, private_data, expires, datetime.now(tz=timezone.utc), res['id'])
            cur.execute(q, q_args)
        conn.commit()
        print(f'Certificate "{name}" updated', file=sys.stderr)
    elif not res:
        with conn.cursor() as cur:
            q = (f"INSERT INTO {schema}.certs "
                 "(name, public_key, private_key, expires, updated) "
                 "VALUES (%s, %s, %s, %s, %s)")
            q_args = (name, public_data, private_data, expires, datetime.now(tz=timezone.utc))
            cur.execute(q, q_args)
        conn.commit()
        print(f'Certificate "{name}" added', file=sys.stderr)
    else:
        print(f'Certificate "{name}" up to date', file=sys.stderr)


def main():
    args = parse_args()
    config = read_config(args.config)
    pg_sync_config = config.get('pg_sync', {})
    schema = pg_sync_config.get('schema', 'public')

    conn = psycopg2.connect(**config['pgsql'])
    create_schema(conn, schema=schema)
    create_tables(conn, schema=schema)
    update_cert(conn, schema, name=args.name, public=args.public_key, private=args.private_key)


if __name__ == '__main__':
    main()
