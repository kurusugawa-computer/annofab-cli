import json
from pathlib import Path
from unittest.mock import Mock

import annofabapi
import pandas
import pytest

from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import print_csv
from annofabcli.input_data.list_all_input_data_merged_task import ListInputDataMergedTask, create_df_input_data_with_merged_task, create_parser


def test_empty_list_outputs_input_data_and_task_headers(tmp_path: Path) -> None:
    output = tmp_path / "input_data.csv"
    print_csv(create_df_input_data_with_merged_task([]), output)

    df = pandas.read_csv(output)
    assert len(df) == 0
    assert {"input_data_id", "input_data_name", "input_data_path", "project_id", "task_id", "task_phase", "task_phase_stage", "task_status", "frame_no"} <= set(df.columns)


@pytest.mark.parametrize(
    ("options", "expected_ids"),
    [
        ([], ["input1", "input2", "input3"]),
        (["--input_data_name", "sAmPlE"], ["input1", "input2"]),
        (["--input_data_name", "sample", "OTHER"], ["input1", "input2", "input3"]),
        (["--input_data_name", "missing"], []),
        (["--input_data_name", "file://{names_file}"], ["input1", "input2"]),
        (["--input_data_name", "file://{names_file}", "--input_data_id", "input2", "input3"], ["input2"]),
        (["--input_data_name", "sample", "--input_data_id", "input2", "input3"], ["input2"]),
        (["--input_data_name", "sample", "--input_data_query", '{"input_data_path": "selected"}'], ["input1"]),
    ],
)
def test_main_filters_input_data_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, options: list[str], expected_ids: list[str]) -> None:
    input_data_list: list[dict[str, object]] = [
        {
            "input_data_id": input_data_id,
            "input_data_name": name,
            "input_data_path": path,
            "project_id": "project1",
            "organization_id": "org1",
            "input_data_set_id": "set1",
            "url": None,
            "etag": None,
            "original_input_data_path": None,
            "updated_datetime": "2026-01-01T00:00:00Z",
            "sign_required": False,
            "metadata": {},
            "system_metadata": {},
        }
        for input_data_id, name, path in [("input1", "Sample-A.jpg", "selected/a.jpg"), ("input2", "sample-B.jpg", "other/b.jpg"), ("input3", "Other.jpg", "selected/c.jpg")]
    ]
    input_data_path = tmp_path / "input_data.json"
    input_data_path.write_text(json.dumps(input_data_list), encoding="utf-8")
    task_path = tmp_path / "tasks.json"
    task_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(DownloadingFile, "download_input_data_json_to_dir", Mock(return_value=input_data_path))
    monkeypatch.setattr(DownloadingFile, "download_task_json_to_dir", Mock(return_value=task_path))
    names_file = tmp_path / "名前一覧.txt"
    names_file.write_text("sAmPlE\n\nmissing\n", encoding="utf-8")
    options = [option.replace("{names_file}", str(names_file)) for option in options]
    output = tmp_path / "result.json"
    args = create_parser().parse_args(["--project_id", "project1", "--format", "json", "--output", str(output), *options])

    ListInputDataMergedTask(Mock(spec=annofabapi.Resource), Mock(spec=AnnofabApiFacade), args).main()

    actual = json.loads(output.read_text(encoding="utf-8"))
    assert [row["input_data_id"] for row in actual] == expected_ids
