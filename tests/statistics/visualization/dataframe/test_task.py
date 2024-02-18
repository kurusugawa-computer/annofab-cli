from pathlib import Path

from annofabcli.statistics.visualization.dataframe.task import Task

output_dir = Path("./tests/out/statistics/visualization/dataframe/task")
data_dir = Path("./tests/data/statistics")
output_dir.mkdir(exist_ok=True, parents=True)


class TestTask:
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
