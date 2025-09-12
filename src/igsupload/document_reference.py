import typer
from datetime import datetime, UTC
import base64

def get_demis_content_type(file_name):
    if file_name.endswith((".fastq", ".fq", ".fastq.gz", ".fq.gz")):
        return "application/fastq"
    elif file_name.endswith((".fasta", ".fa", ".fasta.gz", ".fa.gz")):
        return "application/fasta"
    else:
        raise ValueError(f"{typer.style('Invalid', fg=typer.colors.RED)} fileformat: {file_name}")




def build_document_reference(file_name, sha256_hash):
    return {
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
        "date": datetime.now(UTC).isoformat(),  # z.B. 2025-06-02T18:00:00Z
        "description": f"Sequenzdatei {file_name}",
        "content": [
            {
                "attachment": {
                    "contentType": get_demis_content_type(file_name),
                    "title": file_name,
                    "hash": sha256_hash,
                    "url": ""
                }
            }
        ]
    }
