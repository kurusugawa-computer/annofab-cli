from pathlib import Path

from annofabcli.common.utils import (
    get_file_scheme_path,
    is_file_scheme,
    read_lines_except_blank_line,
    read_multiheader_csv,
)

data_path = Path("./tests/data/utils")


def test_is_file_scheme():
    assert is_file_scheme("file://sample.jpg") is True
    assert is_file_scheme("https://localhost/sample.jpg") is False


def test_get_file_scheme_path():
    assert get_file_scheme_path("file://sample.jpg") == "sample.jpg"
    assert get_file_scheme_path("https://localhost/sample.jpg") is None


def test_get_read_multiheader_csv():
    df = read_multiheader_csv(str(data_path / "multiheader.csv"), header_row_count=2)
    columns = list(df.columns)
    assert columns == [("", "date"), ("task_id", ""), ("worktime", "annotation")]


def test_read_lines_except_blank_line():
    actual = read_lines_except_blank_line(str(data_path / "example-utf8.txt"))
    assert actual == ["a", "あ"]

    # BOM付きでも読み込めるようにする
    actual2 = read_lines_except_blank_line(str(data_path / "example-utf8bom.txt"))
    assert actual2 == ["a", "あ"]
