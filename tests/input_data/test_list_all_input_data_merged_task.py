from pathlib import Path

import pandas

from annofabcli.common.utils import print_csv
from annofabcli.input_data.list_all_input_data_merged_task import create_df_input_data_with_merged_task


def test_empty_list_outputs_input_data_and_task_headers(tmp_path: Path) -> None:
    output = tmp_path / "input_data.csv"
    print_csv(create_df_input_data_with_merged_task([]), output)

    df = pandas.read_csv(output)
    assert len(df) == 0
    assert {"input_data_id", "input_data_name", "input_data_path", "project_id", "task_id", "task_phase", "task_phase_stage", "task_status", "frame_no"} <= set(df.columns)
