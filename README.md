# Sync certs to/from PostgreSQL

### Requirements

These are intended to run as services, you should install the requirements from your package manager,
for example:

```sh
# RHEL
dnf install -y python3-pyOpenSSL python3-psycopg2
# Debian
apt install -y python3-psycopg2 python3-openssl
# Arch
pacman -S python-psycopg2 python-pyopenssl
```

### Database setup

```postgresql
CREATE USER certs_pusher PASSWORD 'certs_pusher';
CREATE DATABASE certs OWNER certs_pusher;
-- Create read-only user to pulling
CREATE USER certs_reader PASSWORD 'certs_reader';
GRANT CONNECT ON DATABASE certs TO certs_reader;
-- Schema should match your config
GRANT USAGE ON SCHEMA public TO certs_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO certs_reader;
-- If you've already created the tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO certs_reader;
```

### Example config

`/etc/pg-cert-store/config.conf`

Keys in pgsql section are passed directly to `psycopg2.connect()`, see [PG docs](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS)
for a complete list

```ini
# This section is mandatory
[pgsql]
host=pg.example.com
dbname=certs
user=certs_pusher
password=certs_pusher

# This section is optional
[pg_sync]
# Defaults to public
schema=certs
# Defaults to /etc/pg-cert-store/hooks.d
hooks_dir=/etc/letsencrypt/renewal-hooks/deploy
```

### Usage with certbot

Install with pip

```sh
pip install --no-deps --install-option="--install-scripts=/usr/local/bin" git+https://github.com/cosandr/pg-cert-store.git
```

Make sure you add the config file as described above.

Add a deploy hook to `/etc/letsencrypt/renewal-hooks/deploy/pg-cert-push`

```sh
#!/bin/sh

/usr/local/bin/pg-cert-push \
    --name "$(basename "$RENEWED_LINEAGE")" \
    --public-key "${RENEWED_LINEAGE}/fullchain.pem" \
    --private-key "${RENEWED_LINEAGE}/privkey.pem"
```

### Testing

Generate self-signed certificate

```sh
openssl req -x509 -newkey rsa:4096 -keyout test/push.key -out test/push.crt -sha256 -days 365 -nodes -subj '/CN=localhost'
```

Place connection details to a PG server in a `test/pg_cert_sync.conf` file.

Run with

```shell
python -m pg_cert_store.push --config test/pg_cert_sync.conf --name test --public-key test/push.crt --private-key test/push.key
python -m pg_cert_store.pull --config test/pg_cert_sync.conf --name test --public-key test/pull.crt --private-key test/pull.key
```

### Author

Andrei Costescu
