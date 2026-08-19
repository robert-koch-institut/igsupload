import typer
from datetime import datetime, UTC

from igsupload.fhir_constants import SEQUENCE_DOCUMENT_PROFILE

def get_demis_content_type(file_name):
    # documentation: https://simplifier.net/rki.demis.igs/contenttype
    if file_name.endswith((".fastq", ".fq")):
        return "chemical/seq-na-fastq"
    elif (file_name.endswith(".fastq.gz", ".fq.gz")):
        return "chemical/seq-na-fastq-gzip"
    elif file_name.endswith((".fasta", ".fa")):
        return "chemical/seq-na-fasta"
    elif file_name.endswith((".fasta.gz", ".fa.gz")):
        return "chemical/seq-na-fasta-gzip"
    else:
        raise ValueError(f"{typer.style('Invalid', fg=typer.colors.RED)} fileformat: {file_name}")



def build_document_reference(file_name, sha256_hash):
    return {
        "resourceType": "DocumentReference",
        "status": "current",
        "meta": {
            "profile": [
                SEQUENCE_DOCUMENT_PROFILE
            ]
        },
        "type": {
            "coding": [
                {
                    "system": "http://snomed.info/sct",
                    "code": "41482005",
                    "display": "Molecular sequence data (finding)"
                }
            ]
        },
        "date": datetime.now(UTC).isoformat(),  # z.B. 2025-06-02T18:00:00Z
        "description": f"Sequenzdatei {file_name}",
        "content": [
            {
                "attachment": {
                    "contentType": get_demis_content_type(file_name),
                    "title": file_name,
                    "hash": sha256_hash
                }
            }
        ]
    }
