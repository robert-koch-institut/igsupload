import os
from getpass import getpass
from pathlib import Path

from cryptography.hazmat.primitives.serialization import (
    BestAvailableEncryption,
    pkcs12,
)

source = Path("client.p12")
target = Path("client-normalized.p12")

password = getpass("PKCS#12 password: ").encode("utf-8")

key, cert, additional_certs = pkcs12.load_key_and_certificates(
    source.read_bytes(),
    password,
)

if key is None or cert is None:
    raise ValueError("Certificate or private key missing")

normalized_data = pkcs12.serialize_key_and_certificates(
    name=b"igsupload",
    key=key,
    cert=cert,
    cas=additional_certs,
    encryption_algorithm=BestAvailableEncryption(password),
)

fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "wb") as file:
    file.write(normalized_data)