import csv
import shutil
from pathlib import Path

from annofabcli.__main__ import main

data_dir = Path("./tests/data/stat_visualization")
out_dir = Path("./tests/out/stat_visualization")


def _append_added_whole_performance_rows(csv_file: Path) -> None:
    added_rows = [
        ["monitored_worktime_hour/task_count", "annotation", "0.8110311255707763"],
        ["monitored_worktime_hour/task_count", "acceptance", "0.5379413527032779"],
        ["actual_worktime_hour/task_count", "annotation", "0.3372330938345292"],
        ["actual_worktime_hour/task_count", "acceptance", "0.22328194413293812"],
        ["monitored_worktime_hour/task_count__lastweek", "annotation", "nan"],
        ["monitored_worktime_hour/task_count__lastweek", "acceptance", "nan"],
        ["monitored_worktime_hour/input_data_count__lastweek", "annotation", "nan"],
        ["monitored_worktime_hour/input_data_count__lastweek", "acceptance", "nan"],
        ["monitored_worktime_hour/annotation_count__lastweek", "annotation", "nan"],
        ["monitored_worktime_hour/annotation_count__lastweek", "acceptance", "nan"],
        ["actual_worktime_hour/task_count__lastweek", "annotation", "nan"],
        ["actual_worktime_hour/task_count__lastweek", "acceptance", "nan"],
        ["actual_worktime_hour/input_data_count__lastweek", "annotation", "nan"],
        ["actual_worktime_hour/input_data_count__lastweek", "acceptance", "nan"],
        ["actual_worktime_hour/annotation_count__lastweek", "annotation", "nan"],
        ["actual_worktime_hour/annotation_count__lastweek", "acceptance", "nan"],
    ]

    with csv_file.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(added_rows)


class TestCommandLine:
    def test__mask_user_info(self):
        main(
            [
                "stat_visualization",
                "mask_user_info",
                "--dir",
                str(data_dir / "mask_visualization_dir/visualization1"),
                "--output_dir",
                str(out_dir / "mask_user_info-out"),
                "--minimal",
            ]
        )

    def test__merge(self):
        main(
            [
                "stat_visualization",
                "merge",
                "--dir",
                str(data_dir / "merge_visualization_dir/visualization1"),
                str(data_dir / "merge_visualization_dir/visualization1"),
                "--output_dir",
                str(out_dir / "merge-out"),
                "--minimal",
            ]
        )

    def test__summarize_whole_performance_csv(self, tmp_path):
        input_dir = tmp_path / "summarize_whole_performance_csv"
        shutil.copytree(data_dir / "summarize_whole_performance_csv", input_dir)
        _append_added_whole_performance_rows(input_dir / "visualization1/全体の生産性と品質.csv")

        main(
            [
                "stat_visualization",
                "summarize_whole_performance_csv",
                "--dir",
                str(input_dir),
                "--output",
                str(tmp_path / "summarize_whole_performance_csv-out.csv"),
            ]
        )

    def test_write_performance_rating_csv(self):
        main(
            [
                "stat_visualization",
                "write_performance_rating_csv",
                "--dir",
                str(data_dir / "write_performance_rating_csv"),
                "--output_dir",
                str(out_dir / "write_performance_rating_csv-out"),
            ]
        )
