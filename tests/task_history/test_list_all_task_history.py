from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pandas

from annofabcli.task_history.list_all_task_history import ListTaskHistoryWithJson
from annofabcli.task_history.list_task_history import CSV_COLUMNS


def test_empty_list_outputs_csv_header(tmp_path: Path) -> None:
    source = tmp_path / "histories.json"
    source.write_text('{"task1": []}')
    output = tmp_path / "histories.csv"
    args = Namespace(project_id="project1", task_id=None, task_history_json=source, temp_dir=None, format="csv", output=output, yes=True)

    ListTaskHistoryWithJson(Mock(), Mock(), args).main()

    df = pandas.read_csv(output)
    assert len(df) == 0
    assert df.columns.to_list() == list(CSV_COLUMNS)
