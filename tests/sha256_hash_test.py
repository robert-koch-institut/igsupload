import tempfile
import pytest
import os

from src.igsupload import sha256_hash

def test_create_hash_file():
    # Schreibe eine kleine Testdatei
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"abc")
        tmp_path = tmp.name

    try:
        result = sha256_hash.create_hash(tmp_path)
        # Erwarteter SHA256-Hash von b"abc"
        expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        assert result == expected
    finally:
        os.remove(tmp_path)

def test_create_hash_empty_file():
    # Leere Datei
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = sha256_hash.create_hash(tmp_path)
        # SHA256 von leerer Datei
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert result == expected
    finally:
        os.remove(tmp_path)

def test_create_hash_file_not_found():
    # Datei existiert nicht
    with pytest.raises(FileNotFoundError):
        sha256_hash.create_hash("/tmp/does_not_exist_123456")
