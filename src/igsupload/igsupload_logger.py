import csv
import os
import errno
from pathlib import Path
from datetime import datetime

base_dir = os.getcwd()
logging_path = base_dir

def set_logging_path(path: str):
    global logging_path

    if path is None:
        return
    raw = str(path).strip()
    if raw == "" or raw.lower() in {"none", "null", "nil"}:
        return

    resolved_path = Path(str(path))
    resolved_path = Path(os.path.expandvars(str(resolved_path))).expanduser()
    try:
        resolved_path = resolved_path.resolve(strict=False)
    except Exception:
        resolved_path = resolved_path.absolute()

    if resolved_path.exists() and not resolved_path.is_dir():
        raise NotADirectoryError(f"Path exists and is not a directory: {resolved_path}")

    try:
        os.makedirs(resolved_path, exist_ok=True)
    except OSError as e:
        if e.errno == errno.EACCES:
            raise PermissionError(f"No permission to create directory: {resolved_path}") from e
        raise FileNotFoundError(f"Invalid path: {resolved_path}") from e

    testfile = resolved_path / ".write_test"
    try:
        with open(testfile, "w", encoding="utf-8") as f:
            f.write("test")
        os.remove(testfile)
    except PermissionError as e:
        raise PermissionError(f"No permission to write to directory: {resolved_path}") from e
    except OSError as e:
        raise OSError(f"Unable to write to directory: {resolved_path}") from e

    logging_path = str(resolved_path)
    print(f"[INFO] Logging directory set to: {logging_path}")

def log_to_csv(
    filename: str,
    notification_id: str,
    transaction_id: str,
    lab_sequence_id: str,
    document_reference_id: str,
    status: str,
    extra_fields: dict = None,
    csv_path: str = None
):

    logging_dir = os.path.join(logging_path, "logging")
    os.makedirs(logging_dir, exist_ok=True) 

    if not csv_path:
        csv_path = os.path.join(logging_dir, "igsupload_log.csv")

    fieldnames = [
        'timestamp',
        'filename',
        'notification_id',
        'transaction_id',
        'lab_sequence_id',
        'document_reference_id',
        'status',
    ]
    if extra_fields:
        fieldnames += list(extra_fields.keys())

    file_exists = os.path.isfile(csv_path)

    with open(csv_path, mode='a', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        row = {
            'timestamp': datetime.now().isoformat(),
            'filename': filename,
            'notification_id': notification_id,
            'transaction_id': transaction_id,
            'lab_sequence_id': lab_sequence_id,
            'document_reference_id': document_reference_id,
            'status': status,
        }
        if extra_fields:
            row.update(extra_fields)
        writer.writerow(row)

def extract_param(parameters, name):
    """
    Hilfsfunktion: Extrahiert einen Parameterwert aus der Demis-Response-Liste.
    """
    for param in parameters:
        if param.get('name') == name:
            value_identifier = param.get('valueIdentifier')
            if value_identifier and 'value' in value_identifier:
                return value_identifier['value']
    return None
