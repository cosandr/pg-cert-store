import configparser
from datetime import timezone
from io import TextIOWrapper
from cryptography import x509


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


def get_cert_expiry(cert: str):
    return x509.load_pem_x509_certificate(cert.encode()).not_valid_after.replace(tzinfo=timezone.utc)
