import datetime
import os
import secrets
import tempfile

import requests
from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    Encoding,
    PrivateFormat,
    pkcs12,
)
from urllib3.util import create_urllib3_context


def _check_cert_not_after(cert):
    cert_not_after = cert.not_valid_after_utc
    if cert_not_after < datetime.datetime.now(datetime.UTC):
        raise ValueError(
            "Client certificate expired: Not After: {cert_not_after:%Y-%m-%d %H:%M:%SZ}".format(
                **locals()
            )
        )


def _create_sslcontext(pkcs12_data, pkcs12_password_bytes):
    private_key, cert, ca_certs = pkcs12.load_key_and_certificates(
        pkcs12_data, pkcs12_password_bytes
    )
    _check_cert_not_after(cert)
    ssl_context = create_urllib3_context()
    ssl_context.load_default_certs()
    with tempfile.NamedTemporaryFile(delete=False) as temp_cert_file:
        try:
            tmp_pkcs12_password_bytes = secrets.token_bytes(128 // 8)
            key_pem = private_key.private_bytes(
                Encoding.PEM,
                PrivateFormat.PKCS8,
                BestAvailableEncryption(password=tmp_pkcs12_password_bytes),
            )
            temp_cert_file.write(key_pem)
            cert_pem = cert.public_bytes(Encoding.PEM)
            temp_cert_file.write(cert_pem)
            if ca_certs:
                for ca_cert in ca_certs:
                    _check_cert_not_after(ca_cert)
                    cert_pem = ca_cert.public_bytes(Encoding.PEM)
                    temp_cert_file.write(cert_pem)
            temp_cert_file.flush()
            temp_cert_file.close()
            ssl_context.load_cert_chain(
                temp_cert_file.name, password=tmp_pkcs12_password_bytes
            )
        finally:
            os.remove(temp_cert_file.name)
    return ssl_context


class Pkcs12Adapter(requests.adapters.HTTPAdapter):
    def __init__(self, *args, pkcs12_path: str, password: str, **kwargs):

        if pkcs12_path is None:
            raise ValueError('"pkcs12_path" is missing')
        if pkcs12_path is not None:
            with open(pkcs12_path, "rb") as pkcs12_file:
                pkcs12_data = pkcs12_file.read()

        # convert pkcs12 password to none/bytes
        if password is None:
            pkcs12_password_bytes = None
        elif isinstance(password, str):
            pkcs12_password_bytes = password.encode("utf8")
        else:
            raise TypeError("Password must be None or a string.")

        self.ssl_context = _create_sslcontext(pkcs12_data, pkcs12_password_bytes)
        super().__init__(*args, **kwargs)  # vllt hier rein

    def init_poolmanager(self, *args, **kwargs) -> None:
        """Initialize a urllib3 PoolManager, using the default SSL certificates on Windows."""
        kwargs["ssl_context"] = self.ssl_context

        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        if self.ssl_context:
            kwargs["ssl_context"] = self.ssl_context
        return super().proxy_manager_for(*args, **kwargs)


class Pkcs12ClientCertSession(requests.Session):
    def __init__(self, pkcs12_path: str, password: str, **kwargs) -> None:
        """
        requests.Session subclass that uses the RKI SSL root certificates setup.

        :param timeout: Request timeout in seconds.
        :param pool_maxsize: Max size of the internal connection pool.
        """
        super().__init__()

        # Pkcs12 Setup
        self.adapter = Pkcs12Adapter(
            pkcs12_path=pkcs12_path, password=password, **kwargs
        )
        self.mount("http://", self.adapter)
        self.mount("https://", self.adapter)
