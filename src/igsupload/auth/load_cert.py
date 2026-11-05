import os
import platform
import datetime
import secrets
import tempfile
import requests

from urllib3.util import create_urllib3_context
from getpass import getpass
from pathlib import Path
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    pkcs12,
    PrivateFormat,
    Encoding,
)

def _check_cert_not_after(cert):
    cert_not_after = cert.not_valid_after_utc
    if cert_not_after < datetime.datetime.now(datetime.timezone.utc):
        raise ValueError('Client certificate expired: Not After: {cert_not_after:%Y-%m-%d %H:%M:%SZ}'.format(**locals()))

def _create_sslcontext(pkcs12_data, pkcs12_password_bytes):
    private_key, cert, ca_certs = pkcs12.load_key_and_certificates(
        pkcs12_data,
        pkcs12_password_bytes
    )
    _check_cert_not_after(cert)
    ssl_context = create_urllib3_context()
    ssl_context.load_default_certs()
    with tempfile.NamedTemporaryFile(delete=False) as c:
        try:
            tmp_pkcs12_password_bytes = secrets.token_bytes(128//8)
            pk_buf = private_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.PKCS8,
                BestAvailableEncryption(password=tmp_pkcs12_password_bytes)
            )
            c.write(pk_buf)
            buf = cert.public_bytes(Encoding.PEM)
            c.write(buf)
            if ca_certs:
                for ca_cert in ca_certs:
                    _check_cert_not_after(ca_cert)
                    buf = ca_cert.public_bytes(Encoding.PEM)
                    c.write(buf)
            c.flush()
            c.close()
            ssl_context.load_cert_chain(c.name, password=tmp_pkcs12_password_bytes)
        finally:
            os.remove(c.name)
    return ssl_context


class Pkcs12Adapter(requests.adapters.HTTPAdapter):
    def __init__(self, *args, **kwargs):
        pkcs12_path = kwargs.pop('pkcs12_path', None)
        pkcs12_password = kwargs.pop('password', None)
        
        
        if pkcs12_path is None:
            raise ValueError('"pkcs12_path" is missing')
        if pkcs12_path is not None:
            with open(pkcs12_path, 'rb') as pkcs12_file:
                pkcs12_data = pkcs12_file.read()
        
        # convert pkcs12 password to none/bytes
        if pkcs12_password is None:
            pkcs12_password_bytes = None
        elif isinstance(pkcs12_password, bytes):
            pkcs12_password_bytes = pkcs12_password
        elif isinstance(pkcs12_password, str):
            pkcs12_password_bytes = pkcs12_password.encode('utf8')
        else:
            raise TypeError('Password must be a None, string or bytes.')

        self.ssl_context = _create_sslcontext(pkcs12_data, pkcs12_password_bytes)
        super(Pkcs12Adapter, self).__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs) -> None:
        """Initialize a urllib3 PoolManager, using the default SSL certificates on Windows."""
        kwargs["ssl_context"] = self.ssl_context

        return super(Pkcs12Adapter, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        if self.ssl_context:
            kwargs['ssl_context'] = self.ssl_context
        return super(Pkcs12Adapter, self).proxy_manager_for(*args, **kwargs)


class RkiSession(requests.Session):
    def __init__(self, **kwargs) -> None:
        """
        requests.Session subclass that uses the RKI SSL root certificates setup.

        :param timeout: Request timeout in seconds.
        :param pool_maxsize: Max size of the internal connection pool.
        """
        super().__init__()

        # Pkcs12 Setup
        self.adapter = Pkcs12Adapter(**kwargs)
        self.mount("http://", self.adapter)
        self.mount("https://", self.adapter)