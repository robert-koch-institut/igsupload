# IGSUpload - CLI zum Upload von Daten für die Integrierte Genomische Surveillance

CLI for the upload of sequencing data (FASTQ, FASTA, FASTQ.GZIP) using the DEMIS API of the Robert Koch Institute (RKI).

## Table of Contents

- [IGSUpload - CLI zum Upload von Daten für die Integrierte Genomische Surveillance](#igsupload---cli-zum-upload-von-daten-für-die-integrierte-genomische-surveillance)
  - [Table of Contents](#table-of-contents)
  - [Description](#description)
  - [Requirements](#requirements)
    - [DEMIS Environments](#demis-environments)
  - [Installation](#installation)
    - [Prerequisites](#prerequisites)
    - [igsupload Setup](#igsupload-setup)
    - [Run igsupload](#run-igsupload)
    - [Development (optional)](#development-optional)
    - [Configure credentials (.env)](#configure-credentials-env)
  - [Usage](#usage)
    - [Final upload report](#final-upload-report)
  - [Project Structure](#project-structure)
  - [Common Issues and Solutions](#common-issues-and-solutions)
    - [Issue: ProxyError or 403 Forbidden](#issue-proxyerror-or-403-forbidden)
    - [Issue: Validation failed ("Hash does not match")](#issue-validation-failed-hash-does-not-match)
    - [Issue: Validation failed ("Invalid file format")](#issue-validation-failed-invalid-file-format)
  - [Testing](#testing)
  - [Authors](#authors)

## Description

This project automates the submission of sequencing data and associated metadata to the DEMIS environment provided by the Robert Koch Institute (RKI). It includes automation for:

1. Authentication with DEMIS
2. Processing metadata files (CSV)
3. Calculating SHA-256 hash values for sequence files
4. Generating FHIR DocumentReferences
5. Uploading sequence files in chunks using presigned URLs
6. Validation of uploaded files
7. Creation and transmission of the final IGS notification (FHIR Bundle)

## Requirements

- Python 3.13 or higher
- Access to the DEMIS (test) environment (including required certificates [demis-support@rki.de](demis-support@rki.de))
- Installation of all dependencies

### DEMIS Environments

| Environment | API Base-URL |
| :--------: | :-------- |
| **Prod** | [https://demis.rki.de/surveillance/notification-sequence](https://demis.rki.de/surveillance/notification-sequence) |
| **Test** | [https://test.demis.rki.de/qs/surveillance/notification-sequence](https://test.demis.rki.de/qs/surveillance/notification-sequence) |

## Installation

### Prerequisites

- [uv](https://docs.astral.sh/uv/) installed on your system
- Git

### igsupload Setup

```bash
git clone https://github.com/robert-koch-institut/igsupload.git
cd igsupload
uv sync
```

This automatically creates a virtual environment and installs all dependencies.


### Run igsupload

```bash
uv run igsupload --help
```

Alternatively, activate the virtual environment to use the `igsupload` command directly:

```bash
source .venv/bin/activate
igsupload --help
```

To deactivate the virtual environment:

```bash
deactivate
```

---

### Development (optional)

Development dependencies, including pytest and Ruff, are already installed by the default `uv sync` command.

Run the test suite:

```bash
uv run pytest
```

Run tests with coverage:

```bash
uv run pytest --cov=src
```

Check code quality:

```bash
uv run ruff check .
```

Format the code:

```bash
uv run ruff format .
```

### Configure credentials (.env)

Modify the .env file with your credentials. Use the **.env.template** file as a template for yours:

```bash
PKCS12_PATH="path/to/cert.p12
PASSWORD="password"

# more infos regarding the Client_Id and Client_Secret is here:
# https://wiki.gematik.de/spaces/DSKB/pages/471343260/Endpunkte+Zertifikate+User+und+Passwort
CLIENT_ID="your-demis-adapter"
CLIENT_SECRET="your-client-secret"
USERNAME="your-username"

BASE_URL="https://API-Base-URL"
TOKEN_URL="https://TOKEN-Base-URL"
```

## Usage

Start the upload process:
With this upload command the application expects a .env file in your root folder

```bash
igsupload --csv /path/to/metadata.csv
```

You can also set a different Path to your .env file with following command:

```bash
igsupload --csv /path/to/metadata.csv --config /path/to/.env
```

In the end, important IDs will be logged in a csv-File. Therefore a folder called "logging" is created in the root project directory. If you want to set a individual path to save the logs, use the "--log" flag to specify it.

```bash
igsupload --csv /path/to/metadata.csv --config /path/to/.env --log /path/to/logs
```

Show a small introduction with:

```bash
igsupload intro
```

### Final upload report

Every run creates an `igsupload_report.csv` file in its logging directory. The
report contains exactly one row for every data row in the metadata CSV. The
`metadata_row` counter starts at `1` and does not include the CSV header.

The report is updated after every important processing step. This means that
the latest state is still available if the application is interrupted.

The following status values are used:

- `PENDING`: The metadata row has not been processed yet.
- `IN_PROGRESS`: The metadata row is currently being processed.
- `SUCCESS`: Upload, validation, and notification completed successfully.
- `FAILED`: Processing failed. See `stage`, `error_type`, and `message`.
- `NEEDS_REVIEW`: DEMIS accepted the notification, but the expected response data
  is missing or not complete. Do not resend automatically before checking the report.

The fields `filenames`, `sha256_values`, `document_reference_ids`, `upload_ids`,
and `validation_statuses` contain JSON arrays. Their entries use the same file
order. Each array contains one or two values, depending on the number of
sequence files in the metadata row.

## Project Structure

```bash
igs-upload/
|   cert/                                 # contains certificates
├── src/
│   └── igsupload/
│       ├── __init__.py
│       ├── config.py                     # Configuration and certificates
│       ...
│       ├── workflow.py                   # Main project workflow
│       └── main.py                       # Entry point (CLI)
├── data/
│   ├── metadata/
│   │   └── IGS_metadata_test_data.csv
│   └── reads/
│       ├── Sample12346_R1.fastq
│       └── Sample12346_R2.fastq
├── tests/                                # unit tests
├── .env
├── .gitignore                           
├── setup.py                              # for pip
├── LICENSE
└── README.md
```

## Common Issues and Solutions

### Issue: ProxyError or 403 Forbidden

- Ensure access to the DEMIS test environment is available from your network.

### Issue: Validation failed ("Hash does not match")

- Files must not change after hash calculation.

- Verify files were not altered after hash calculation.

- wrong fastq/fastq.gzip file structure

### Issue: Validation failed ("Invalid file format")

- Supported formats: FASTA, FASTQ, and their GZIP-compressed forms.

- Verify file extensions and integrity.

## Authors

- Lukas Karsten ([KarstenL@rki.de](KarstenL@rki.de))
- Felix Hartkopf ([HartkopfF@rki.de](HartkopfF@rki.de))
