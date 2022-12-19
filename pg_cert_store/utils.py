import configparser
from datetime import datetime, timezone
from io import TextIOWrapper

import OpenSSL


def read_config(f: TextIOWrapper) -> dict:
    config = configparser.ConfigParser()
    config.read_file(f)
    f.close()
    if not config.has_section('pgsql'):
        print('Config file is missing pgsql section', file=sys.stderr)
        exit(1)
    ret = {}
    for s in config.sections():
        ret[s] = {k: v for k, v in config.items(s)}
    return ret


def get_cert_expiry(cert):
    x509 = OpenSSL.crypto.load_certificate(OpenSSL.crypto.FILETYPE_PEM, cert)
    return datetime.strptime(x509.get_notAfter().decode(), "%Y%m%d%H%M%SZ").replace(tzinfo=timezone.utc)
