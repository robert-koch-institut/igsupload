import uuid
import re
import requests
import typer
import json
from datetime import datetime, timezone

import igsupload.config as config
import igsupload.get_token as token_module
from igsupload.extract_csv import CsvRow

IGS_SPEC_BASE = "https://demis.rki.de/fhir/igs"
NOTIFICATION_ID_SYSTEM = "https://demis.rki.de/fhir/NamingSystem/NotificationId"
NOTIFICATION_BUNDLE_ID_SYSTEM = "https://demis.rki.de/fhir/NamingSystem/NotificationBundleId"
NOTIFIED_PERSON_ANONYMOUS_PROFILE = "https://demis.rki.de/fhir/StructureDefinition/NotifiedPersonAnonymous"
ADDRESS_USE_EXTENSION = "https://demis.rki.de/fhir/StructureDefinition/AddressUse"
ADDRESS_USE_SYSTEM = "https://demis.rki.de/fhir/CodeSystem/addressUse"
ADAPTER_SUBSTANCE_PROFILE = f"{IGS_SPEC_BASE}/StructureDefinition/AdapterSubstance"
PRIMER_SUBSTANCE_PROFILE = f"{IGS_SPEC_BASE}/StructureDefinition/PrimerSubstance"
SEQUENCING_SUBSTANCES_SYSTEM = f"{IGS_SPEC_BASE}/CodeSystem/sequencingSubstances"
LOINC_VERSION = "2.79"
SNOMED_CT_VERSION = "http://snomed.info/sct/11000274103/version/20241115"
# Temporarily disabled: TEST-QS profile V5 has a known additive slicing bug.
INCLUDE_SEQUENCING_ADDITIVES = True


def _fhir_base() -> str:
    if not config.BASE_URL:
        raise RuntimeError("BASE_URL is not set. Load config first (via --config or .env).")
    return config.BASE_URL.rstrip("/") + "/v5/fhir"


def _nz(value):
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _fmt_date_or_datetime(value: str) -> str | None:
    v = _nz(value)
    if not v:
        return None
    if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])(-([0-2]\d|3[01]))?", v):
        return v
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", v):
        try:
            dt = datetime.strptime(v, "%d.%m.%Y").date()
            return dt.isoformat()
        except ValueError:
            return None
    return None


def _fmt_birth_year_month(year: str, month: str) -> str | None:
    y = _nz(year)
    m = _nz(month)
    if not y or not m:
        return None
    if not re.fullmatch(r"(19|20)\d{2}", y):
        return None
    if not re.fullmatch(r"(0[1-9]|1[0-2])", m):
        return None
    return f"{y}-{m}"


def _valid_email(e: str) -> bool:
    s = _nz(e)
    return bool(s and "@" in s and "." in s.split("@")[-1])


def _required_uuid(value: str, field_name: str) -> str:
    """Return a canonical UUID or fail early for a required DEMIS identifier."""
    candidate = _nz(value)
    if not candidate:
        raise ValueError(f"{field_name} must contain a UUID")
    try:
        return str(uuid.UUID(candidate))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"{field_name} must contain a valid UUID") from exc


def _new_uuid_excluding(*excluded_values: str) -> str:
    excluded = set(excluded_values)
    while True:
        candidate = str(uuid.uuid4())
        if candidate not in excluded:
            return candidate


def _sequencing_substance_entry(
    substance_id: str,
    profile: str,
    category_code: str,
    value: str,
) -> dict:
    # IGS 5.0 distinguishes adapter and primer through category.coding.
    # Both Substance profiles explicitly prohibit code.coding.
    return {
        "fullUrl": f"{IGS_SPEC_BASE}/Substance/{substance_id}",
        "resource": {
            "resourceType": "Substance",
            "id": substance_id,
            "meta": {"profile": [profile]},
            "category": [{
                "coding": [{
                    "system": SEQUENCING_SUBSTANCES_SYSTEM,
                    "code": category_code,
                }]
            }],
            "code": {"text": value},
        },
    }


def _prune(obj):
    if isinstance(obj, dict):
        cleaned = {}
        for k, v in obj.items():
            v_clean = _prune(v)
            if v_clean is None:
                continue
            if v_clean == "":
                continue
            if isinstance(v_clean, (list, dict)) and not v_clean:
                continue
            cleaned[k] = v_clean
        return cleaned
    if isinstance(obj, list):
        cleaned_list = []
        for v in obj:
            v_clean = _prune(v)
            if v_clean is None:
                continue
            if v_clean == "":
                continue
            if isinstance(v_clean, (list, dict)) and not v_clean:
                continue
            cleaned_list.append(v_clean)
        return cleaned_list
    return obj


VALID_GENDERS = {"male", "female", "other", "unknown"}
SNOMED_UPLOAD_STATUS = {
    "accepted": "385645004",
    "planned": "397943006",
    "denied": "441889009",
    "other": "74964007"
}
SEQ_REASON_TO_SNOMED = {
    "random": "255226008",
    "requested": "385644000",
    "clinical": "58147004",
    "other": "74964007"
}


def build_notification_bundle(row: CsvRow, doc_ids: [str]) -> dict:
    referenced_notification_id = _required_uuid(
        row.DEMIS_NOTIFICATION_ID,
        "DEMIS_NOTIFICATION_ID",
    )
    notification_id = _new_uuid_excluding(referenced_notification_id)
    notification_bundle_id = _new_uuid_excluding(
        referenced_notification_id,
        notification_id,
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    patient_id = str(uuid.uuid4())
    organization_id = str(uuid.uuid4())
    practitioner_role_id = str(uuid.uuid4())

    # --- Adapter-Parsing ---
    adapters = []
    if _nz(row.ADAPTER):
        adapters = [
            adapter.strip()
            for adapter in row.ADAPTER.split("+", 1)
            if adapter.strip()
        ]

    # --- Notifier/Sequenzierlabor ---
    org_identifier_value = _nz(row.SEQUENCING_LAB_DEMIS_LAB_ID)
    org_name = _nz(row.SEQUENCING_LAB_NAME) or "Unknown laboratory"
    org_email = row.SEQUENCING_LAB_EMAIL if _valid_email(row.SEQUENCING_LAB_EMAIL) else "noreply@example.org"
    org_address_line = _nz(row.SEQUENCING_LAB_ADDRESS) or "Unknown street 1"
    org_city = _nz(row.SEQUENCING_LAB_CITY) or "Unbekannt"
    org_postal = _nz(row.SEQUENCING_LAB_POSTAL_CODE) or "00000"
    org_state = _nz(row.SEQUENCING_LAB_FEDERAL_STATE) or "DE-XX"

    org_resource = {
        'resourceType': 'Organization',
        'id': organization_id,
        'meta': {'profile': ['https://demis.rki.de/fhir/StructureDefinition/NotifierFacility']},
        **({
            'identifier': [{
                'system': 'https://demis.rki.de/fhir/NamingSystem/DemisLaboratoryId',
                'value': org_identifier_value
            }]
        } if org_identifier_value else {}),
        "type": [{
            "coding": [{
                "system": "https://demis.rki.de/fhir/CodeSystem/organizationType",
                "code": "refLab",
                "display": "Einrichtung der Spezialdiagnostik"
            }]
        }],
        'name': org_name,
        "telecom": [{"system": "email", "value": org_email, "use": "work"}],
        'address': [{
            'line': [org_address_line],
            'city': org_city,
            'postalCode': org_postal,
            'country': 'DE',
            "state": org_state,
        }]
    }

    org_entry = {
        'fullUrl': f'{IGS_SPEC_BASE}/Organization/{organization_id}',
        'resource': org_resource
    }

    practitioner_role_entry = {
        'fullUrl': f'{IGS_SPEC_BASE}/PractitionerRole/{practitioner_role_id}',
        'resource': {
            'resourceType': 'PractitionerRole',
            'id': practitioner_role_id,
            'meta': {'profile': ['https://demis.rki.de/fhir/StructureDefinition/NotifierRole']},
            'organization': {'reference': f'Organization/{organization_id}'}
        }
    }

    # --- Submitting (Primär-/Diagnostiklabor aus CSV) ---
    submitting_org_id = str(uuid.uuid4())
    submitting_role_id = str(uuid.uuid4())

    sub_name  = _nz(row.PRIME_DIAGNOSTIC_LAB_NAME)
    sub_email = row.PRIME_DIAGNOSTIC_LAB_EMAIL if _valid_email(row.PRIME_DIAGNOSTIC_LAB_EMAIL) else None
    sub_addr  = _nz(row.PRIME_DIAGNOSTIC_LAB_ADDRESS)
    sub_city  = _nz(row.PRIME_DIAGNOSTIC_LAB_CITY)
    sub_post  = _nz(row.PRIME_DIAGNOSTIC_LAB_POSTAL_CODE)
    sub_labid = _nz(row.PRIME_DIAGNOSTIC_LAB_DEMIS_LAB_ID)
    sub_state = _nz(row.PRIME_DIAGNOSTIC_LAB_FEDERAL_STATE) or "DE-XX"

    has_telecom = bool(sub_email)
    has_address = bool(sub_addr or sub_city or sub_post)
    can_claim_submitting_profile = has_telecom and has_address

    submitting_org_resource = {
        "resourceType": "Organization",
        "id": submitting_org_id,
        **({"meta": {"profile": ["https://demis.rki.de/fhir/StructureDefinition/SubmittingFacility"]}}
           if can_claim_submitting_profile else {}),
        **({
            "identifier": [{
                "system": "https://demis.rki.de/fhir/NamingSystem/DemisLaboratoryId",
                "value": sub_labid
            }]
        } if sub_labid else {}),
        **({"name": sub_name} if sub_name else {}),
        **({"telecom": [{"system": "email", "value": sub_email, "use": "work"}]}
            if has_telecom else {}),
        **({"address": [{
            **({"line": [sub_addr]} if sub_addr else {}),
            **({"city": sub_city} if sub_city else {}),
            **({"postalCode": sub_post} if sub_post else {}),
            **({"state": sub_state} if sub_state else {}),
            "country": "DE"
        }]} if has_address else {})
    }

    submitting_org_present = any(k for k in submitting_org_resource.keys() if k not in {"resourceType", "id", "meta"})
    submitting_org_entry = None
    submitting_role_entry = None

    if submitting_org_present:
        submitting_org_entry = {
            "fullUrl": f"{IGS_SPEC_BASE}/Organization/{submitting_org_id}",
            "resource": submitting_org_resource
        }
        submitting_role_resource = {
            "resourceType": "PractitionerRole",
            "id": submitting_role_id,
            **({"meta": {"profile": ["https://demis.rki.de/fhir/StructureDefinition/SubmittingRole"]}}
               if can_claim_submitting_profile else {}),
            "organization": {"reference": f"Organization/{submitting_org_id}"}
        }
        submitting_role_entry = {
            "fullUrl": f"{IGS_SPEC_BASE}/PractitionerRole/{submitting_role_id}",
            "resource": submitting_role_resource
        }

    # --- Patient ---
    gender = (_nz(row.HOST_SEX) or "").strip().lower()
    gender = gender if gender in VALID_GENDERS else None
    birth_date = _fmt_birth_year_month(row.HOST_BIRTH_YEAR, row.HOST_BIRTH_MONTH)
    geo_postal = _nz(row.GEOGRAPHIC_LOCATION)

    patient_resource = {
        'resourceType': 'Patient',
        'id': patient_id,
        'meta': {'profile': [NOTIFIED_PERSON_ANONYMOUS_PROFILE]},
        **({'gender': gender} if gender else {}),
        **({'birthDate': birth_date} if birth_date else {}),
        **({"address": [{
            "extension": [{
                "url": ADDRESS_USE_EXTENSION,
                "valueCoding": {
                    "system": ADDRESS_USE_SYSTEM,
                    "code": "primary"
                }
            }],
            "postalCode": geo_postal
        }]} if geo_postal else {})
    }

    patient_entry = {
        'fullUrl': f'{IGS_SPEC_BASE}/Patient/{patient_id}',
        'resource': patient_resource
    }

    # --- Sequenzierung ---
    adapter_entries = []
    primer_entry = None
    if INCLUDE_SEQUENCING_ADDITIVES:
        for adapter in adapters:
            adapter_id = str(uuid.uuid4())
            adapter_entries.append(
                _sequencing_substance_entry(
                    substance_id=adapter_id,
                    profile=ADAPTER_SUBSTANCE_PROFILE,
                    category_code="adapter",
                    value=adapter,
                )
            )

        primer_scheme = _nz(row.PRIMER_SCHEME)
        if primer_scheme:
            primer_id = str(uuid.uuid4())
            primer_entry = _sequencing_substance_entry(
                substance_id=primer_id,
                profile=PRIMER_SUBSTANCE_PROFILE,
                category_code="primer",
                value=primer_scheme,
            )

    # --- Specimen ---
    spec_received = _fmt_date_or_datetime(row.DATE_OF_RECEIVING)
    spec_collected = _fmt_date_or_datetime(row.DATE_OF_SAMPLING)
    spec_sequenced = _fmt_date_or_datetime(row.DATE_OF_SEQUENCING)

    specimen_id = str(uuid.uuid4())
    specimen_additives = []
    if INCLUDE_SEQUENCING_ADDITIVES:
        specimen_additives = [
            {"reference": f"Substance/{entry['resource']['id']}"}
            for entry in adapter_entries
        ]
        if primer_entry:
            specimen_additives.append({
                "reference": f"Substance/{primer_entry['resource']['id']}"
            })

    collector_ref = (
        f'PractitionerRole/{submitting_role_id}'
        if submitting_role_entry is not None
        else f'PractitionerRole/{practitioner_role_id}'
    )

    specimen_resource = {
        'resourceType': 'Specimen',
        'id': specimen_id,
        'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/SpecimenSequence']},
        'status': 'available',
        **({
            'extension': [{
                'url': 'https://demis.rki.de/fhir/igs/StructureDefinition/Isolate',
                'valueString': _nz(row.ISOLATE)
            }]
        } if _nz(row.ISOLATE) else {}),
        'type': {
            'coding': [{
                'system': 'http://snomed.info/sct',
                'version': SNOMED_CT_VERSION,
                **({'code': _nz(row.ISOLATION_SOURCE_CODE)} if _nz(row.ISOLATION_SOURCE_CODE) else {}),
                **({'display': _nz(row.ISOLATION_SOURCE)} if _nz(row.ISOLATION_SOURCE) else {})
            }]
        },
        'subject': {'reference': f'Patient/{patient_id}'},
        **({'receivedTime': spec_received} if spec_received else {}),
        'collection': {
            'collector': {'reference': collector_ref},
            **({'collectedDateTime': spec_collected} if spec_collected else {})
        },
        'processing': [{
            **({'description': _nz(row.NAME_AMP_PROTOCOL)} if _nz(row.NAME_AMP_PROTOCOL) else {}),
            **({
                'procedure': {
                    'coding': [{
                        'system': 'https://demis.rki.de/fhir/igs/CodeSystem/sequencingStrategy',
                        'code': _nz(row.SEQUENCING_STRATEGY)
                    }]
                }
            } if _nz(row.SEQUENCING_STRATEGY) else {}),
            **({'additive': specimen_additives} if specimen_additives else {}),
            **({'timeDateTime': spec_sequenced} if spec_sequenced else {})
        }]
    }

    specimen_entry = {
        'fullUrl': f'{IGS_SPEC_BASE}/Specimen/{specimen_id}',
        'resource': specimen_resource
    }

    # --- Device ---
    device_id = str(uuid.uuid4())
    device_resource = {
        'resourceType': 'Device',
        'id': device_id,
        'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/SequencingDevice']},
        **({
            'deviceName': [{'name': _nz(row.SEQUENCING_INSTRUMENT), 'type': 'model-name'}]
        } if _nz(row.SEQUENCING_INSTRUMENT) else {}),
        **({
            'type': {
                'coding': [{
                    'system': 'https://demis.rki.de/fhir/igs/CodeSystem/sequencingPlatform',
                    'code': _nz(row.SEQUENCING_PLATFORM),
                    'display': _nz(row.SEQUENCING_PLATFORM)
                }]
            }
        } if _nz(row.SEQUENCING_PLATFORM) else {})
    }

    device_entry = {
        'fullUrl': f'{IGS_SPEC_BASE}/Device/{device_id}',
        'resource': device_resource
    }

    # --- IDs ---
    observation_id = str(uuid.uuid4())
    diagnostic_report_id = str(uuid.uuid4())
    sequence_id = str(uuid.uuid4())

    # --- Repository ---
    repo_name = (_nz(row.REPOSITORY_NAME) or "").strip().lower()
    if repo_name not in {"gisaid", "ena", "sra", "pubmlst", "genbank", "other"}:
        repo_name = "other"

    raw_status = (_nz(row.UPLOAD_STATUS) or "").strip().lower()
    if raw_status in SNOMED_UPLOAD_STATUS:
        status_code = SNOMED_UPLOAD_STATUS[raw_status]
    elif raw_status in SNOMED_UPLOAD_STATUS.values():
        status_code = raw_status
    else:
        status_code = (
            SNOMED_UPLOAD_STATUS["accepted"]
            if (_nz(row.REPOSITORY_LINK) or _nz(row.REPOSITORY_ID))
            else SNOMED_UPLOAD_STATUS["planned"]
        )

    repo_extensions = [{
        "url": "https://demis.rki.de/fhir/igs/StructureDefinition/SequenceUploadStatus",
        "valueCoding": {
            "system": "http://snomed.info/sct",
            "code": status_code
        }
    }]

    upload_date = _fmt_date_or_datetime(row.UPLOAD_DATE)
    if upload_date:
        repo_extensions.append({
            "url": "https://demis.rki.de/fhir/igs/StructureDefinition/SequenceUploadDate",
            "valueDateTime": upload_date
        })
    if _nz(row.UPLOAD_SUBMITTER):
        repo_extensions.append({
            "url": "https://demis.rki.de/fhir/igs/StructureDefinition/SequenceUploadSubmitter",
            "valueString": _nz(row.UPLOAD_SUBMITTER)
        })

    repository = {
        "name": repo_name,
        **({"url": _nz(row.REPOSITORY_LINK)} if _nz(row.REPOSITORY_LINK) else {}),
        **({"datasetId": _nz(row.REPOSITORY_ID)} if _nz(row.REPOSITORY_ID) else {}),
        "type": "other",
        "extension": repo_extensions
    }

    # --- Sequencing reason & SequenceAuthor ---
    seq_extensions = [{
        "url": "https://demis.rki.de/fhir/igs/StructureDefinition/SequenceDocumentReference",
        "valueReference": {
            "reference": f"{_fhir_base()}/DocumentReference/{doc_ids[0]}",
            "type": "DocumentReference"
        }
    },{
        "url": "https://demis.rki.de/fhir/igs/StructureDefinition/SequenceDocumentReference",
        "valueReference": {
            "reference": f"{_fhir_base()}/DocumentReference/{doc_ids[1]}",
            "type": "DocumentReference"
        }
    }]

    if _nz(row.SEQUENCING_REASON):
        key = _nz(row.SEQUENCING_REASON).lower()
        code = SEQ_REASON_TO_SNOMED.get(key) or (_nz(row.SEQUENCING_REASON) if re.fullmatch(r"\d+", _nz(row.SEQUENCING_REASON)) else None)
        if code:
            seq_extensions.insert(0, {
                "url": "https://demis.rki.de/fhir/igs/StructureDefinition/SequencingReason",
                "valueCoding": {
                    "system": "http://snomed.info/sct",
                    "code": code
                }
            })

    author_txt = _nz(row.AUTHOR)
    if author_txt:
        seq_extensions.insert(0, {
            "url": "https://demis.rki.de/fhir/igs/StructureDefinition/SequenceAuthor",
            "valueString": author_txt
        })

    # --- MolecularSequence ---
    molecular_sequence_resource = {
        'resourceType': 'MolecularSequence',
        'id': sequence_id,
        'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/Sequence']},
        'coordinateSystem': 1,
        'specimen': {'reference': f'Specimen/{specimen_id}'},
        'device': {'reference': f'Device/{device_id}'},
        'extension': seq_extensions,
        **({'identifier': [{"value": _nz(row.LAB_SEQUENCE_ID)}]} if _nz(row.LAB_SEQUENCE_ID) else {}),
        "performer": {"reference": f"Organization/{organization_id}"},
        "repository": [repository]
    }

    molecular_sequence_entry = {
        'fullUrl': f'{IGS_SPEC_BASE}/MolecularSequence/{sequence_id}',
        'resource': molecular_sequence_resource
    }

    # --- Observation ---
    obs_code = _nz(row.SPECIES_CODE)
    obs_display = _nz(row.SPECIES)

    observation_entry = {
        'fullUrl': f'{IGS_SPEC_BASE}/Observation/{observation_id}',
        'resource': {
            'resourceType': 'Observation',
            'id': observation_id,
            'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/PathogenDetectionSequence']},
            **({'status': _nz(row.STATUS)} if _nz(row.STATUS) else {'status': 'final'}),
            'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/observation-category', 'code': 'laboratory'}]}],
            'code': {'coding': [{
                'system': 'http://loinc.org',
                'version': LOINC_VERSION,
                'code': '41852-5',
                'display': 'Microorganism or agent identified in Specimen',
            }]},
            "valueCodeableConcept": {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "version": SNOMED_CT_VERSION,
                            **({'code': obs_code} if obs_code else {}),
                            **({'display': obs_display} if obs_display else {})
                        }
                    ]
                },
            'subject': {'reference': f'Patient/{patient_id}'},
            'interpretation': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation', 'code': 'POS'}]}],
            'method': {'coding': [{
                'system': 'http://snomed.info/sct',
                'version': SNOMED_CT_VERSION,
                'code': '1304162005',
                'display': 'Nucleic acid sequencing technique (qualifier value)'
            }]},
            'specimen': {'reference': f'Specimen/{specimen_id}'},
            'device': {'reference': f'Device/{device_id}'},
            'derivedFrom': [{'reference': f'MolecularSequence/{sequence_id}'}]
        }
    }

    # --- DiagnosticReport ---
    dr_code = _nz(row.MELDETATBESTAND)

    diagnostic_report_entry = {
        'fullUrl': f'{IGS_SPEC_BASE}/DiagnosticReport/{diagnostic_report_id}',
        'resource': {
            'resourceType': 'DiagnosticReport',
            'id': diagnostic_report_id,
            'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/LaboratoryReportSequence']},
            'status': 'final',
            'code': {'coding': [{
                'system': 'https://demis.rki.de/fhir/CodeSystem/notificationCategory',
                **({'code': dr_code} if dr_code else {})
            }]},
            'subject': {'reference': f'Patient/{patient_id}'},
            'issued': now_iso,
            'result': [{'reference': f'Observation/{observation_id}'}],
            'conclusion': 'NACHWEIS eines meldepflichtigen Erregers',
            'conclusionCode': [{
                'coding': [{
                    'system': 'https://demis.rki.de/fhir/CodeSystem/conclusionCode',
                    'code': 'pathogenDetected',
                    'display': 'Meldepflichtiger Erreger nachgewiesen'
                }]
            }]
        }
    }

    # --- Composition ---
    composition_entry = {
        'fullUrl': f'{IGS_SPEC_BASE}/Composition/{notification_id}',
        'resource': {
            'resourceType': 'Composition',
            'id': notification_id,
            'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/NotificationSequence']},
            'identifier': {
                'system': NOTIFICATION_ID_SYSTEM,
                'value': notification_id
            },
            **({'status': _nz(row.STATUS)} if _nz(row.STATUS) else {'status': 'final'}),
            'type': {'coding': [{'system': 'http://loinc.org', 'code': '34782-3', 'display': 'Infectious disease Note'}]},
            'category': [{'coding': [{'system': 'http://loinc.org', 'code': '11502-2', 'display': 'Laboratory report'}]}],
            'subject': {'reference': f'Patient/{patient_id}'},
            'author': [{'reference': f'PractitionerRole/{practitioner_role_id}'}],
            'relatesTo': [{
                'code': 'appends',
                'targetReference': {
                    'type': 'Composition',
                    'identifier': {
                        'system': NOTIFICATION_ID_SYSTEM,
                        'value': referenced_notification_id
                    }
                }
            }],
            'date': now_iso,
            'title': 'Sequenzmeldung',
            'section': [{
                'code': {'coding': [{'system': 'http://loinc.org', 'code': '11502-2', 'display': 'Laboratory report'}]},
                'entry': [{'reference': f'DiagnosticReport/{diagnostic_report_id}'}]
            }]
        }
    }

    # --- Bundle-Entries ---
    entries = [
        composition_entry,
        patient_entry,
        practitioner_role_entry,   # NotifierRole
        org_entry,                 # NotifierFacility
        *( [submitting_role_entry] if submitting_role_entry else [] ),
        *( [submitting_org_entry] if submitting_org_entry else [] ),
        specimen_entry,
        device_entry,
        *adapter_entries,
        *( [primer_entry] if primer_entry else [] ),
        molecular_sequence_entry,
        observation_entry,
        diagnostic_report_entry
    ]

    bundle = {
        'resourceType': 'Bundle',
        'meta': {
            'lastUpdated': now_iso,
            'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/NotificationBundleSequence']
        },
        'identifier': {
            'system': NOTIFICATION_BUNDLE_ID_SYSTEM,
            'value': notification_bundle_id
        },
        'type': 'document',
        'timestamp': now_iso,
        'entry': entries
    }

    return _prune(bundle)


def send_notification(row: CsvRow, doc_ids: [str]) -> dict:
    bundle = build_notification_bundle(
        row=row,
        doc_ids=doc_ids
    )
    
    url = _fhir_base() + "/$process-notification-sequence"
    print(url)
    headers = {
        'Authorization': f'Bearer {token_module.current_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    return requests.post(
        url,
        headers=headers,
        json=bundle,
        cert=(config.CERT, config.KEY),
    )
