import json
from pathlib import Path

import annofabapi
import pandas
import pytest

from annofabcli.statistics.visualization.dataframe.annotation_count import AnnotationCount
from annofabcli.statistics.visualization.dataframe.input_data_count import InputDataCount
from annofabcli.statistics.visualization.dataframe.inspection_comment_count import InspectionCommentCount
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.model import ProductionVolumeColumn

output_dir = Path("./tests/out/statistics/visualization/dataframe/task")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestTask:
    @pytest.mark.access_webapi
    def test__from_api_content(self):
        with open(data_dir / "task.json", encoding="utf-8") as f:
            tasks = json.load(f)

        with open(data_dir / "task-history.json", encoding="utf-8") as f:
            task_histories = json.load(f)

        project_id = "1186bb00-16e6-4d20-8e24-310322911850"

        df_annotation_count = pandas.DataFrame({"project_id": [project_id, project_id], "task_id": ["sample_0", "sample_1"], "annotation_count": [10, 20]})
        annotation_count = AnnotationCount(df_annotation_count)

        df_inspection_comment_count = pandas.DataFrame(
            {
                "project_id": [project_id, project_id],
                "task_id": ["sample_0", "sample_1"],
                "inspection_comment_count": [5, 7],
                "inspection_comment_count_in_inspection_phase": [2, 3],
                "inspection_comment_count_in_acceptance_phase": [3, 4],
            }
        )
        inspection_comment_count = InspectionCommentCount(df_inspection_comment_count)
        actual1 = Task.from_api_content(
            tasks,
            task_histories,
            annotation_count=annotation_count,
            input_data_count=None,
            inspection_comment_count=inspection_comment_count,
            project_id=project_id,
            annofab_service=annofabapi.build(),
        )
        actual1.df.to_csv("out/df.csv")
        assert len(actual1.df) == 2
        row1 = actual1.df.iloc[0]
        assert row1["annotation_count"] == 10
        assert row1["inspection_comment_count"] == 5
        assert row1["input_data_count"] == 2

        input_data_count = InputDataCount(pandas.DataFrame({"project_id": [project_id, project_id], "task_id": ["sample_0", "sample_1"], "input_data_count": [1, 1]}))
        actual2 = Task.from_api_content(
            tasks,
            task_histories,
            annotation_count=annotation_count,
            inspection_comment_count=inspection_comment_count,
            project_id=project_id,
            annofab_service=annofabapi.build(),
            input_data_count=input_data_count,
        )
        assert len(actual2.df) == 2
        row2 = actual2.df.iloc[0]
        assert row2["input_data_count"] == 1

    def test__from_csv__and__to_csv(cls) -> None:
        actual = Task.from_csv(data_dir / "task.csv")
        assert len(actual.df) == 5
        actual.to_csv(output_dir / "test__from_csv__and__to_csv.csv")

    def test__plot_histogram_of_worktime(self):
        obj = Task.from_csv(data_dir / "task.csv")
        obj.plot_histogram_of_worktime(output_dir / "ヒストグラム-作業時間.html")

    def test__plot_histogram_of_others(self):
        obj = Task.from_csv(data_dir / "task.csv")
        obj.plot_histogram_of_others(output_dir / "ヒストグラム.html")

    def test__plot_histogram_of_others__ユーザー独自の生産量をプロット(self):
        obj = Task.from_csv(
            data_dir / "task.csv",
            custom_production_volume_list=[
                ProductionVolumeColumn("custom_production_volume1", "custom_生産量1"),
                ProductionVolumeColumn("custom_production_volume2", "custom_生産量2"),
            ],
        )
        obj.plot_histogram_of_others(output_dir / "ヒストグラム.html")

    def test__merge(self):
        obj = Task.from_csv(data_dir / "task.csv")
        actual = Task.merge(obj, obj)
        assert len(actual.df) == 10

    def test__merge__emptyオブジェクトに対して(self):
        obj = Task.from_csv(data_dir / "task.csv")
        empty = Task.empty()
        assert empty.is_empty()

        merged_obj = Task.merge(empty, obj)
        assert len(obj.df) == len(merged_obj.df)

    def test__mask_user_info(self):
        obj = Task.from_csv(data_dir / "task.csv")
        masked_obj = obj.mask_user_info(
            to_replace_for_user_id={"user1": "masked_user_id"},
            to_replace_for_username={"user1": "masked_username"},
        )

        actual_first_row = masked_obj.df.iloc[0]
        # 一部の列だけ置換されていることを確認する
        assert actual_first_row["first_annotation_user_id"] == "masked_user_id"
        assert actual_first_row["first_annotation_username"] == "masked_username"
