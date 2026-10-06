from pathlib import Path

import pandas

from annofabcli.common.enums import OutputFormat
from annofabcli.common.utils import (
    get_file_scheme_path,
    is_file_scheme,
    print_according_to_format,
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


def test_print_according_to_format_empty_csv(tmp_path, capsys):

    columns = ["project_id", "task_id"]
    output = tmp_path / "empty.csv"
    print_according_to_format([], OutputFormat.CSV, output, csv_columns=columns)
    actual = pandas.read_csv(output)
    assert len(actual) == 0
    assert actual.columns.to_list() == columns

    print_according_to_format([], OutputFormat.CSV, csv_columns=columns)
    assert capsys.readouterr().out == "project_id,task_id\n"


def test_csv_fallback_columns_keep_nonempty_data(tmp_path):

    output = tmp_path / "data.csv"
    records = [{"task_id": "task1", "metadata.customer": "customer1"}]
    print_according_to_format(records, OutputFormat.CSV, output, csv_columns=["project_id", "task_id"])
    assert pandas.read_csv(output).to_dict(orient="records") == records
