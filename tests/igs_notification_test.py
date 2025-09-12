import pytest
import uuid
from datetime import datetime, timezone
from unittest import mock
import igsupload.config as config

from src.igsupload.igs_notification import build_notification_bundle, send_notification

BASE_URL = 'https://demis.rki.de/fhir/igs'
TEST_FILE = "test.fasta"
NOTIFICATION_ID = "not_id"
DOCUMENT_REFERENCE_ID = "doc_id"
LABORATORY_ID = "lab_id"

@pytest.fixture
def mock_send_notification():
    """Fixture, um die Funktion `send_notification` zu mocken."""
    with mock.patch('src.igsupload.igs_notification.requests.post') as mock_post:
        yield mock_post

def test_send_notification_success(mock_send_notification):
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "transactionID": "123",
        "submitterGeneratedNotificationID": "234",
        "labSequenceID": "567"
    }
    mock_send_notification.return_value = mock_response

    result = send_notification(TEST_FILE, DOCUMENT_REFERENCE_ID, "LAB123")
    
    assert result["transactionID"] == "123"
    assert result["submitterGeneratedNotificationID"] == "234"
    assert result["labSequenceID"] == "567"

    mock_send_notification.assert_called_once()

def test_send_notification_value_error(mock_send_notification):
    mock_response = mock.Mock()
    mock_response.status_code = 400
    mock_response.json.side_effect = ValueError("No JSON could be decoded")
    mock_response.text = "Some error text"
    mock_response.raise_for_status.side_effect = Exception("HTTP error!")
    mock_send_notification.return_value = mock_response

    # Build-Bundle auch mocken
    with mock.patch('src.igsupload.igs_notification.build_notification_bundle', return_value={}):
        import src.igsupload.igs_notification as module
        module.config.CERT = "foo"
        module.config.KEY = "bar"
        module.token_module.current_token = "dummy"

        with pytest.raises(Exception, match="HTTP error!"):
            send_notification("test.fasta", "doc_id", "lab_id")

def test_build_notification_bundle():
    # Reihenfolge der UUID-Generierung exakt wie im Code!
    fake_uuids = [
        "00000000-0000-0000-0000-000000000001",  # patient_id
        "00000000-0000-0000-0000-000000000002",  # organization_id
        "00000000-0000-0000-0000-000000000003",  # practitioner_role_id
        "00000000-0000-0000-0000-000000000004",  # adapter1_id
        "00000000-0000-0000-0000-000000000005",  # adapter2_id
        "00000000-0000-0000-0000-000000000006",  # primer_id
        "00000000-0000-0000-0000-000000000007",  # device_id
        "00000000-0000-0000-0000-000000000008",  # specimen_id
        "00000000-0000-0000-0000-000000000009",  # observation_id
        "00000000-0000-0000-0000-000000000010",  # diagnostic_report_id
        "00000000-0000-0000-0000-000000000011",  # sequence_id
    ]
    uuid_iter = iter(fake_uuids)
    fixed_now = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    fixed_now_iso = fixed_now.isoformat()

    with mock.patch('src.igsupload.igs_notification.uuid.uuid4', side_effect=lambda: next(uuid_iter)):
        with mock.patch('src.igsupload.igs_notification.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_now
            mock_datetime.now.timezone = timezone
            mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
            
            # Bundle bauen
            bundle = build_notification_bundle(
                file_name=TEST_FILE,
                notification_id=NOTIFICATION_ID,
                doc_id=DOCUMENT_REFERENCE_ID,
                lab_id=LABORATORY_ID
            )

    expected_entries = [
        {
            'fullUrl': f'{BASE_URL}/Composition/{NOTIFICATION_ID}',
            'resource': {
                'resourceType': 'Composition',
                'id': NOTIFICATION_ID,
                'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/NotificationSequence']},
                'identifier': {'system': 'https://demis.rki.de/fhir/NamingSystem/NotificationId', 'value': NOTIFICATION_ID},
                'status': 'final',
                'type': {'coding': [{'system': 'http://loinc.org', 'code': '34782-3', 'display': 'Infectious disease Note'}]},
                'category': [{'coding': [{'system': 'http://loinc.org', 'code': '11502-2', 'display': 'Laboratory report'}]}],
                'subject': {'reference': f'Patient/{fake_uuids[0]}'},
                'author': [{'reference': f'PractitionerRole/{fake_uuids[2]}'}],
                'relatesTo': [{
                    'code': 'appends',
                    'targetReference': {
                        'type': 'Composition',
                        'identifier': {'system': 'https://demis.rki.de/fhir/NamingSystem/NotificationId', 'value': NOTIFICATION_ID}
                    }
                }],
                'date': fixed_now_iso,
                'title': 'Sequenzmeldung',
                'section': [{
                    'code': {'coding': [{'system': 'http://loinc.org', 'code': '11502-2', 'display': 'Laboratory report'}]},
                    'entry': [{'reference': f'DiagnosticReport/{fake_uuids[9]}'}]
                }]
            }
        },
        {
            'fullUrl': f'{BASE_URL}/Patient/{fake_uuids[0]}',
            'resource': {
                'resourceType': 'Patient',
                'id': fake_uuids[0],
                'meta': {'profile': ['https://demis.rki.de/fhir/StructureDefinition/NotifiedPersonNotByName']}
            }
        },
        {
            'fullUrl': f'{BASE_URL}/PractitionerRole/{fake_uuids[2]}',
            'resource': {
                'resourceType': 'PractitionerRole',
                'id': fake_uuids[2],
                'meta': {'profile': ['https://demis.rki.de/fhir/StructureDefinition/NotifierRole']},
                'organization': {'reference': f'Organization/{fake_uuids[1]}'}
            }
        },
        {
            'fullUrl': f'{BASE_URL}/Organization/{fake_uuids[1]}',
            'resource': {
                'resourceType': 'Organization',
                'id': fake_uuids[1],
                'meta': {'profile': ['https://demis.rki.de/fhir/StructureDefinition/NotifierFacility']},
                'identifier': [{
                    'system': 'https://demis.rki.de/fhir/NamingSystem/DemisLaboratoryId',
                    'value': LABORATORY_ID
                }],
                "type": [
                    {
                        "coding": [
                            {
                                "system": "https://demis.rki.de/fhir/CodeSystem/organizationType",
                                "code": "refLab",
                                "display": "Einrichtung der Spezialdiagnostik"
                            }
                        ]
                    }
                ],
                'name': 'Beispiel-Labor',
                "telecom": [
                    {
                        "system": "email",
                        "value": "NRZ-Influenza@rki.de",
                        "use": "work"
                    }
                ],
                'address': [{
                    'line': ['Seestr. 10'],
                    'city': 'Berlin',
                    'postalCode': '13353',
                    'country': 'DE'
                }]
            }
        },
        {
            'fullUrl': f'{BASE_URL}/Specimen/{fake_uuids[7]}',
            'resource': {
                'resourceType': 'Specimen',
                'id': fake_uuids[7],
                'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/SpecimenSequence']},
                'status': 'available',
                'type': {
                    'coding': [{
                        'system': 'http://snomed.info/sct',
                        'code': '258604001',
                        'display': 'Upper respiratory specimen (specimen)'
                    }]
                },
                'subject': {'reference': f'Patient/{fake_uuids[0]}'},
                'receivedTime': fixed_now_iso,
                'collection': {
                    'collector': {'reference': f'PractitionerRole/{fake_uuids[2]}'},
                    'collectedDateTime': fixed_now_iso
                },
                'processing': [{
                    'description': 'nCoV-2019 sequencing protocol',
                    'procedure': {
                        'coding': [{
                            'system': 'https://demis.rki.de/fhir/igs/CodeSystem/sequencingStrategy',
                            'code': 'amplicon'
                        }]
                    },
                    'additive': [
                        {'reference': f'Substance/{fake_uuids[3]}'},
                        {'reference': f'Substance/{fake_uuids[4]}'},
                        {'reference': f'Substance/{fake_uuids[5]}'}
                    ],
                    'timeDateTime': fixed_now_iso
                }]
            }
        },
        {
            'fullUrl': f'{BASE_URL}/Device/{fake_uuids[6]}',
            'resource': {
                'resourceType': 'Device',
                'id': fake_uuids[6],
                'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/SequencingDevice']},
                'deviceName': [{'name': 'Illumina_MiSeq', 'type': 'model-name'}],
                'type': {
                    'coding': [{
                        'system': 'https://demis.rki.de/fhir/igs/CodeSystem/sequencingPlatform',
                        'code': 'illumina',
                        'display': 'Illumina'
                    }]
                }
            }
        },
        {
            'fullUrl': f'{BASE_URL}/Substance/{fake_uuids[3]}',
            'resource': {
                'resourceType': 'Substance',
                'id': fake_uuids[3],
                'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/AdapterSubstance']},
                'code': {'coding': [{
                    'system': 'https://demis.rki.de/fhir/igs/CodeSystem/sequencingSubstances',
                    'code': 'adapter', 'display': 'Adapter Sequence'
                }]},
                'description': 'AGATCGGAAGAG'
            }
        },
        {
            'fullUrl': f'{BASE_URL}/Substance/{fake_uuids[4]}',
            'resource': {
                'resourceType': 'Substance',
                'id': fake_uuids[4],
                'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/AdapterSubstance']},
                'code': {'coding': [{
                    'system': 'https://demis.rki.de/fhir/igs/CodeSystem/sequencingSubstances',
                    'code': 'adapter', 'display': 'Adapter Sequence'
                }]},
                'description': 'CTCTTCCGATCT'
            }
        },
        {
            'fullUrl': f'{BASE_URL}/Substance/{fake_uuids[5]}',
            'resource': {
                'resourceType': 'Substance',
                'id': fake_uuids[5],
                'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/PrimerSubstance']},
                'code': {'coding': [{
                    'system': 'https://demis.rki.de/fhir/igs/CodeSystem/sequencingSubstances',
                    'code': 'primer', 'display': 'Primer Sequence'
                }]},
                'description': 'ARTICv4.1 ...'
            }
        },
        {
            'fullUrl': f'{BASE_URL}/MolecularSequence/{fake_uuids[10]}',
            'resource': {
                'resourceType': 'MolecularSequence',
                'id': fake_uuids[10],
                'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/Sequence']},
                'coordinateSystem': 1,
                'specimen': {'reference': f'Specimen/{fake_uuids[7]}'},
                'device': {'reference': f'Device/{fake_uuids[6]}'},
                'extension': [
                    {
                        "url": "https://demis.rki.de/fhir/igs/StructureDefinition/SequenceDocumentReference",
                        "valueReference": {
                            "reference": f"{config.BASE_URL}/fhir/DocumentReference/{DOCUMENT_REFERENCE_ID}",
                            "type": "DocumentReference"
                        }
                    }
                ],
                "identifier": [{"value": "A384"}],
                "performer": {"reference": f"Organization/{fake_uuids[1]}"}
            }
        },
        {
            'fullUrl': f'{BASE_URL}/Observation/{fake_uuids[8]}',
            'resource': {
                'resourceType': 'Observation',
                'id': fake_uuids[8],
                'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/PathogenDetectionSequence']},
                'status': 'final',
                'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/observation-category', 'code': 'laboratory'}]}],
                'code': {'coding': [{'system': 'http://loinc.org', 'code': '96741-4', 'display': 'SARS-CoV-2 (COVID-19) variant Sequencing Nom (Specimen)'}]},
                'subject': {'reference': f'Patient/{fake_uuids[0]}'},
                'valueString': 'BA.2',
                'interpretation': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation', 'code': 'POS'}]}],
                'method': {'coding': [{'system': 'http://snomed.info/sct', 'code': '117040002', 'display': 'Nucleic acid sequencing (procedure)'}]},
                'specimen': {'reference': f'Specimen/{fake_uuids[7]}'},
                'device': {'reference': f'Device/{fake_uuids[6]}'},
                'derivedFrom': [{'reference': f'MolecularSequence/{fake_uuids[10]}'}]
            }
        },
        {
            'fullUrl': f'{BASE_URL}/DiagnosticReport/{fake_uuids[9]}',
            'resource': {
                'resourceType': 'DiagnosticReport',
                'id': fake_uuids[9],
                'meta': {'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/LaboratoryReportSequence']},
                'status': 'final',
                'code': {'coding': [{
                    'system': 'https://demis.rki.de/fhir/CodeSystem/notificationCategory',
                    'code': 'cvdp',
                    'display': 'Severe-Acute-Respiratory-Syndrome-Coronavirus-2 (SARS-CoV-2)'
                }]},
                'subject': {'reference': f'Patient/{fake_uuids[0]}'},
                'issued': fixed_now_iso,
                'result': [{'reference': f'Observation/{fake_uuids[8]}'}],
                'conclusion': 'NACHWEIS eines meldepflichtigen Erregers',
                'conclusionCode': [{
                    'coding': [{
                        'system': 'https://demis.rki.de/fhir/CodeSystem/conclusionCode',
                        'code': 'pathogenDetected',
                        'display': 'Meldepflichtiger Erreger nachgewiesen'
                    }]
                }]
            }
        },
    ]

    expected_result = {
        'resourceType': 'Bundle',
        'meta': {
            'lastUpdated': fixed_now_iso,
            'profile': ['https://demis.rki.de/fhir/igs/StructureDefinition/NotificationBundleSequence']
        },
        'identifier': {
            'system': 'https://demis.rki.de/fhir/NamingSystem/NotificationBundleId',
            'value': NOTIFICATION_ID
        },
        'type': 'document',
        'timestamp': fixed_now_iso,
        'entry': expected_entries
    }

    assert bundle == expected_result