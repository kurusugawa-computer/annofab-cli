from pathlib import Path

from annofabcli.common.utils import get_file_scheme_path, is_file_scheme, read_multiheader_csv

out_path = Path("./tests/out/utils")
data_path = Path("./tests/data/utils")


def test_is_file_scheme():
    assert is_file_scheme("file://sample.jpg") == True
    assert is_file_scheme("https://localhost/sample.jpg") == False


def test_get_file_scheme_path():
    assert get_file_scheme_path("file://sample.jpg") == "sample.jpg"
    assert get_file_scheme_path("https://localhost/sample.jpg") is None


def test_get_read_multiheader_csv():
    df = read_multiheader_csv(str(data_path / "multiheader.csv"), header_row_count=2)
    columns = list(df.columns)
    assert columns == [("", "date"), ("task_id", ""), ("worktime", "annotation")]
