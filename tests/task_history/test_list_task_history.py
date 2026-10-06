from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pandas

from annofabcli.task_history.list_task_history import CSV_COLUMNS, ListTaskHistory


def test_empty_list_outputs_csv_header(tmp_path: Path) -> None:
    service = Mock()
    service.wrapper.get_task_histories_or_none.return_value = []
    output = tmp_path / "histories.csv"
    args = Namespace(project_id="project1", task_id=["task1"], format="csv", output=output, yes=True)

    ListTaskHistory(service, Mock(), args).main()

    df = pandas.read_csv(output)
    assert len(df) == 0
    assert df.columns.to_list() == list(CSV_COLUMNS)
