DEMIS_FHIR_BASE = "https://demis.rki.de/fhir"
IGS_FHIR_BASE = f"{DEMIS_FHIR_BASE}/igs"


def demis_profile(name: str) -> str:
    return f"{DEMIS_FHIR_BASE}/StructureDefinition/{name}"


def igs_profile(name: str) -> str:
    return f"{IGS_FHIR_BASE}/StructureDefinition/{name}"


def demis_code_system(name: str) -> str:
    return f"{DEMIS_FHIR_BASE}/CodeSystem/{name}"


def igs_code_system(name: str) -> str:
    return f"{IGS_FHIR_BASE}/CodeSystem/{name}"


def demis_naming_system(name: str) -> str:
    return f"{DEMIS_FHIR_BASE}/NamingSystem/{name}"


# Resource profiles
NOTIFICATION_BUNDLE_PROFILE = igs_profile("NotificationBundleSequence")
NOTIFICATION_PROFILE = igs_profile("NotificationSequence")
NOTIFIED_PERSON_ANONYMOUS_PROFILE = demis_profile("NotifiedPersonAnonymous")
DIAGNOSTIC_REPORT_PROFILE = igs_profile("LaboratoryReportSequence")
SPECIMEN_PROFILE = igs_profile("SpecimenSequence")
OBSERVATION_PROFILE = igs_profile("PathogenDetectionSequence")
MOLECULAR_SEQUENCE_PROFILE = igs_profile("Sequence")
ADAPTER_SUBSTANCE_PROFILE = igs_profile("AdapterSubstance")
PRIMER_SUBSTANCE_PROFILE = igs_profile("PrimerSubstance")
SEQUENCING_DEVICE_PROFILE = igs_profile("SequencingDevice")
SEQUENCE_DOCUMENT_PROFILE = igs_profile("SequenceDocument")
NOTIFIER_FACILITY_PROFILE = demis_profile("NotifierFacility")
NOTIFIER_ROLE_PROFILE = demis_profile("NotifierRole")
SUBMITTING_FACILITY_PROFILE = demis_profile("SubmittingFacility")
SUBMITTING_ROLE_PROFILE = demis_profile("SubmittingRole")

# Naming systems
NOTIFICATION_ID_SYSTEM = demis_naming_system("NotificationId")
NOTIFICATION_BUNDLE_ID_SYSTEM = demis_naming_system("NotificationBundleId")
DEMIS_LABORATORY_ID_SYSTEM = demis_naming_system("DemisLaboratoryId")

# Extensions
ADDRESS_USE_EXTENSION = demis_profile("AddressUse")
ISOLATE_EXTENSION = igs_profile("Isolate")
SEQUENCE_UPLOAD_STATUS_EXTENSION = igs_profile("SequenceUploadStatus")
SEQUENCE_UPLOAD_DATE_EXTENSION = igs_profile("SequenceUploadDate")
SEQUENCE_UPLOAD_SUBMITTER_EXTENSION = igs_profile("SequenceUploadSubmitter")
SEQUENCE_DOCUMENT_REFERENCE_EXTENSION = igs_profile("SequenceDocumentReference")
SEQUENCING_REASON_EXTENSION = igs_profile("SequencingReason")
SEQUENCE_AUTHOR_EXTENSION = igs_profile("SequenceAuthor")

# DEMIS/IGS code systems
ADDRESS_USE_SYSTEM = demis_code_system("addressUse")
ORGANIZATION_TYPE_SYSTEM = demis_code_system("organizationType")
NOTIFICATION_CATEGORY_SYSTEM = demis_code_system("notificationCategory")
CONCLUSION_CODE_SYSTEM = demis_code_system("conclusionCode")
SEQUENCING_SUBSTANCES_SYSTEM = igs_code_system("sequencingSubstances")
SEQUENCING_STRATEGY_SYSTEM = igs_code_system("sequencingStrategy")
SEQUENCING_PLATFORM_SYSTEM = igs_code_system("sequencingPlatform")

# Terminology baseline used by the DEMIS package under evaluation
LOINC_VERSION = "2.79"
SNOMED_CT_VERSION = "http://snomed.info/sct/11000274103/version/20241115"
