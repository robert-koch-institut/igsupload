import hashlib

import pytest

from igsupload.utils.sha256_hash import create_hash


def test_create_hash_reads_complete_binary_file(tmp_path):
    content = (b"ACGT" * 5000) + b"final"
    file_path = tmp_path / "sample.fq.gz"
    file_path.write_bytes(content)

    assert create_hash(file_path) == hashlib.sha256(content).hexdigest()


def test_create_hash_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_hash(tmp_path / "missing.fastq")
