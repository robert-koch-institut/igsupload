import pytest
import csv

from src.igsupload import extract_csv

def test_read_csv(tmp_path):
    data = "name;age\nAlice;30\nBob;25"
    
    test_file_path = tmp_path / "test_data" / "metadata"
    test_file_path.mkdir(parents=True)

    file_path = test_file_path / "test_data.csv"
    file_path.write_text(data, encoding="utf-8")

    result = extract_csv.read_csv(str(file_path))

    assert result == [
        {'name': 'Alice', 'age': '30'},
        {'name': 'Bob', 'age': '25'}
    ]
