import pytest

from igsupload.builders.document_reference import get_demis_content_type


@pytest.mark.parametrize(
    ("file_name", "expected_content_type"),
    [
        ("sample.fastq.gz", "chemical/seq-na-fastq-gzip"),
        ("sample.fq.gz", "chemical/seq-na-fastq-gzip"),
        ("sample.fasta.gz", "chemical/seq-na-fasta-gzip"),
        ("sample.fa.gz", "chemical/seq-na-fasta-gzip"),
    ],
)
def test_get_demis_content_type_for_gzip_files(
    file_name,
    expected_content_type,
):
    assert get_demis_content_type(file_name) == expected_content_type
