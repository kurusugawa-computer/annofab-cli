import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock

import pandas
import pytest

from annofabcli.common.download import DownloadingFile
from annofabcli.task_history.list_all_task_history import ListTaskHistoryWithJson, ListTaskHistoryWithJsonMain
from annofabcli.task_history.list_task_history import CSV_COLUMNS


def test_empty_list_outputs_csv_header(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "histories.json"
    source.write_text('{"task1": []}')
    output = tmp_path / "histories.csv"
    args = Namespace(project_id="project1", task_id=None, temp_dir=None, format="csv", output=output, yes=True)

    monkeypatch.setattr(DownloadingFile, "download_task_history_json_to_dir", Mock(return_value=source))
    ListTaskHistoryWithJson(Mock(), Mock(), args).main()

    df = pandas.read_csv(output)
    assert len(df) == 0
    assert df.columns.to_list() == list(CSV_COLUMNS)


@pytest.mark.parametrize("use_temp_dir", [False, True])
def test_downloaded_histories_are_filtered_and_enriched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, use_temp_dir: bool) -> None:
    histories = {"task1": [{"account_id": None, "accumulated_labor_time_milliseconds": "PT1H"}], "task2": []}

    def download(project_id: str, dest_dir: Path) -> Path:
        assert project_id == "project1"
        path = dest_dir / "histories.json"
        path.write_text(json.dumps(histories), encoding="utf-8")
        return path

    monkeypatch.setattr(DownloadingFile, "download_task_history_json_to_dir", Mock(side_effect=download))
    result = ListTaskHistoryWithJsonMain(Mock()).get_task_history_dict("project1", task_id_list=["task1"], temp_dir=tmp_path if use_temp_dir else None)

    assert list(result) == ["task1"]
    assert result["task1"][0]["worktime_hour"] == 1
    assert result["task1"][0]["user_id"] is None
