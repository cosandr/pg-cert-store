#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys

import psycopg2
import psycopg2.extensions
from psycopg2.extras import RealDictCursor

from .utils import read_config, get_cert_expiry

class CertificateNotFoundError(Exception):
    def __init__(self, name: str):
        self.name = name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Pull certs from PGSQL')
    parser.add_argument('-c', '--config', type=argparse.FileType('r'), default='/etc/pg-cert-store/config.conf', help='Path to config file')
    parser.add_argument('-n', '--name', required=True, help='Name of certificate')
    parser.add_argument('-p', '--public-key', required=True, help='Path to public key')
    parser.add_argument('-k', '--private-key', required=True, help='Path to private key')
    parser.add_argument('-f', '--force', action='store_true', help='Always pull certificates')
    return parser.parse_args()


def get_cert(conn: psycopg2.extensions.connection, schema: str, name: str, public: str, private: str, force: bool = False) -> bool:
    """Returns True if certificate was changed, False otherwise"""
    # Check if cert exists
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT id, expires FROM {schema}.certs WHERE name=%s", (name,))
        res = cur.fetchone()
    if not res:
        raise CertificateNotFoundError(name)
    # Check if a certificate exists already
    if not force and os.path.exists(public):
        with open(public, 'r') as f:
            existing_expires = get_cert_expiry(f.read())
        # Don't do anything if the expiry date is the same
        if existing_expires == res['expires']:
            print(f'Certificate "{name}" is up to date', file=sys.stderr)
            return False
    # Certificate doesn't exist or was updated
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(f"SELECT public_key, private_key FROM {schema}.certs WHERE id=%s", (res['id'],))
        new_data = cur.fetchone()
    print(f'Got new certificate "{name}" expiring at {res["expires"]}', file=sys.stderr)
    with open(public, 'w') as f:
        f.write(new_data['public_key'])
    print(f'Wrote public key "{public}"', file=sys.stderr)
    with open(private, 'w') as f:
        f.write(new_data['private_key'])
    print(f'Wrote private key "{private}"', file=sys.stderr)
    return True


def run_hooks(hooks_dir: str):
    if not os.path.exists(hooks_dir):
        print(f'"{hooks_dir}" does not exist, skipping hooks', file=sys.stderr)
        return

    for f in os.listdir(hooks_dir):
        abs_path = os.path.join(hooks_dir, f)
        print(f'Running "{abs_path}"', file=sys.stderr)
        try:
            subprocess.run(abs_path, check=True)
        except Exception as e:
            print(f'WARNING: Hook "{abs_path}" failed to run: {e}', file=sys.stderr)


def main():
    args = parse_args()
    config = read_config(args.config)
    pg_sync_config = config.get('pg_sync', {})
    schema = pg_sync_config.get('schema', 'public')
    hooks_dir = pg_sync_config.get('hooks_dir', '/etc/pg-cert-store/hooks.d')

    conn = psycopg2.connect(**config['pgsql'])
    changed = False
    try:
        changed = get_cert(conn, schema, name=args.name, public=args.public_key, private=args.private_key, force=args.force)
    except CertificateNotFoundError as e:
        print(f'Certificate "{e.name}" not found in database', file=sys.stderr)
        return 1

    if changed:
        run_hooks(hooks_dir)

    return 0


if __name__ == '__main__':
    exit(main())
