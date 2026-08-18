# IGSUpload - CLI zum Upload von Daten für die Integrierte Genomische Surveillance

CLI for the upload of sequencing data (FASTQ, FASTA, FASTQ.GZIP) using the DEMIS API of the Robert Koch Institute (RKI).

## Table of Contents

- [IGSUpload - CLI zum Upload von Daten für die Integrierte Genomische Surveillance](#igsupload---cli-zum-upload-von-daten-für-die-integrierte-genomische-surveillance)
  - [Table of Contents](#table-of-contents)
  - [Description](#description)
  - [Requirements](#requirements)
    - [DEMIS Environments](#demis-environments)
  - [Installation](#installation)
    - [Clone the repository](#clone-the-repository)
    - [Set up the virtual environment](#set-up-the-virtual-environment)
    - [Install dependencies](#install-dependencies)
    - [Optional (Developers only)](#optional-developers-only)
    - [Configure credentials (.env)](#configure-credentials-env)
  - [Usage](#usage)
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

### Clone the repository

```bash
git clone https://github.com/robert-koch-institut/igsupload.git
cd igs-upload
```

### Set up the virtual environment

There are different ways of creating a virtual environment.
Setup with **venv**:

```bash
python -m venv venv
source venv/bin/activate
```

You can also use **conda** if installed:

```bash
conda create --name igsupload python=3.13
conda activate igsupload
```

### Install dependencies

User can install all dependencies via PyPi:

```bash
pip install igsupload
```

If you cloned the Repository you can also install everything with:

```bash
pip install .
```

---

### Optional (Developers only)

```bash
pip install -e .[dev]
```
This option is used, if you want to install and execute pytest. 

---

### Configure credentials (.env)

Modify the .env file with your credentials. Use the **.env.template** file as a template for yours:

```bash
CERT_URL="/url/to/cert.pem"
KEY_URL="/url/to/key.pem"

# more infos regarding the Client_Id and Client_Secret is here:
# https://wiki.gematik.de/spaces/DSKB/pages/471343260/Endpunkte+Zertifikate+User+und+Passwort
CLIENT_ID="your-demis-adapter"
CLIENT_SECRET="your-client-secret"
USERNAME="your-username"

BASE_URL="https://API-Base-URL"
```

You will probably receive a .p12 certificate from DEMIS. For this appiclication you will need a key.pem and cert.pem file. With these two bash commands you are able to convert the .p12 certificate in the key.pem and cert.pem files.

```bash
# <path-to-p12> = Pfad zur .p12-Datei
openssl pkcs12 -in <path-to-p12> -clcerts -nokeys -out cert.pem --legacy

openssl pkcs12 -in <path-to-p12> -nocerts -nodes -out key.pem --legacy
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
igs upload --csv /path/to/metadata.csv --config /path/to/.env --log /path/to/new/log.csv
```

Show a small introduction with:

```bash
igsupload intro
```

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

- Check your network and proxy settings.

- Ensure access to the DEMIS test environment is available from your network.

### Issue: Validation failed ("Hash does not match")

- Files must not change after hash calculation.

- Verify files were not altered after hash calculation.

- wrong fastq/fastq.gzip file structure

### Issue: Validation failed ("Invalid file format")

- Supported formats: FASTA, FASTQ, and their GZIP-compressed forms.

- Verify file extensions and integrity.

## Testing

Run tests with pytest:

```bash
pytest tests/
```

For Coverage:

```bash
pytest --cov=src
```

## Authors

- Lukas Karsten ([KarstenL@rki.de](KarstenL@rki.de))
- Felix Hartkopf ([HartkopfF@rki.de](HartkopfF@rki.de))
