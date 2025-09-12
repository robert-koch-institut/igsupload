import pytest
from unittest import mock
from datetime import datetime
import requests
import time

from src.igsupload import document_reference as dc_manager

def test_get_demis_content_type():
    fastq_response = dc_manager.get_demis_content_type("test.fastq")
    fasta_response = dc_manager.get_demis_content_type("test.fasta")

    assert fastq_response == "application/fastq"
    assert fasta_response == "application/fasta"
    with pytest.raises(ValueError):
        dc_manager.get_demis_content_type("error.txt")

def test_build_document_reference():
    fake_time = datetime(2023, 1, 1, 12, 0, 0)
    test_file = "test.fastq"
    hash = "test_hash"

    expected_result = {
        "resourceType": "DocumentReference",
        "status": "current",
        "type": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "258207000",
                    "display": "Molecular sequence data (finding)"
                }
            ]
        },
        "date": fake_time.isoformat(),
        "description": f"Sequenzdatei {test_file}",
        "content": [
            {
                "attachment": {
                    "contentType": "application/fastq",
                    "title": test_file,
                    "hash": hash,
                    "url": ""
                }
            }
        ]
    }

    with mock.patch("src.igsupload.document_reference.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_time
        mock_datetime.utcnow.return_value = fake_time

        doc_reference = dc_manager.build_document_reference(test_file, hash)

    assert doc_reference == expected_result
