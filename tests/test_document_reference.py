from datetime import datetime

import pytest

from igsupload.builders.document_reference import (
    build_document_reference,
    get_demis_content_type,
)
from igsupload.builders.fhir_constants import SEQUENCE_DOCUMENT_PROFILE


@pytest.mark.parametrize(
    ("file_name", "content_type"),
    [
        ("sample.fastq", "chemical/seq-na-fastq"),
        ("sample.fq", "chemical/seq-na-fastq"),
        ("sample.fastq.gz", "chemical/seq-na-fastq-gzip"),
        ("sample.fq.gz", "chemical/seq-na-fastq-gzip"),
        ("sample.fasta", "chemical/seq-na-fasta"),
        ("sample.fa", "chemical/seq-na-fasta"),
        ("sample.fasta.gz", "chemical/seq-na-fasta-gzip"),
        ("sample.fa.gz", "chemical/seq-na-fasta-gzip"),
    ],
)
def test_supported_sequence_formats_have_demis_content_type(
    file_name,
    content_type,
):
    assert get_demis_content_type(file_name) == content_type


def test_unknown_sequence_format_is_rejected():
    with pytest.raises(ValueError, match="fileformat"):
        get_demis_content_type("sample.txt")


def test_document_reference_contains_file_identity_and_profile():
    result = build_document_reference("sample.fq.gz", "abc123")
    attachment = result["content"][0]["attachment"]

    assert result["resourceType"] == "DocumentReference"
    assert result["meta"]["profile"] == [SEQUENCE_DOCUMENT_PROFILE]
    assert result["status"] == "current"
    assert attachment == {
        "contentType": "chemical/seq-na-fastq-gzip",
        "title": "sample.fq.gz",
        "hash": "abc123",
    }
    assert datetime.fromisoformat(result["date"]).tzinfo is not None
