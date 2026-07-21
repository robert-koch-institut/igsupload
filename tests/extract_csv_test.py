from igsupload.extract_csv import CsvRow, read_csv


def test_read_csv_returns_cleaned_csv_rows(tmp_path):
    csv_file = tmp_path / "metadata.csv"
    csv_file.write_text(
        "MELDETATBESTAND;SPECIES_CODE;SPECIES;FILE_1_NAME;FILE_2_NAME\n"
        " cvdp ; 3092008 ; Staphylococcus aureus ; sample_R1.fastq ; "
        "sample_R2.fastq \n",
        encoding="utf-8",
    )

    result = read_csv(str(csv_file))

    assert len(result) == 1
    assert isinstance(result[0], CsvRow)
    assert result[0].MELDETATBESTAND == "cvdp"
    assert result[0].SPECIES_CODE == "3092008"
    assert result[0].SPECIES == "Staphylococcus aureus"
    assert result[0].FILE_1_NAME == "sample_R1.fastq"
    assert result[0].FILE_2_NAME == "sample_R2.fastq"
    assert result[0].LAB_SEQUENCE_ID == ""


def test_read_csv_ignores_unknown_columns(tmp_path):
    csv_file = tmp_path / "metadata.csv"
    csv_file.write_text(
        "MELDETATBESTAND;UNKNOWN_COLUMN\ncvdp;ignored\n",
        encoding="utf-8",
    )

    result = read_csv(str(csv_file))

    assert len(result) == 1
    assert result[0].MELDETATBESTAND == "cvdp"
    assert not hasattr(result[0], "UNKNOWN_COLUMN")
