import os
from pathlib import Path

from annofabcli.__main__ import main

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/stat_visualization")
out_dir = Path("./tests/out/stat_visualization")


class TestCommandLine:
    def test_mask_user_info(self):
        main(
            [
                "stat_visualization",
                "mask_user_info",
                "--dir",
                str(data_dir),
                "--output_dir",
                str(out_dir / "mask_user_info-out"),
                "--minimal",
            ]
        )

    def test_merge(self):
        main(
            [
                "stat_visualization",
                "merge",
                "--dir",
                str(data_dir / "visualization-dir"),
                str(data_dir / "visualization-dir"),
                "--output_dir",
                str(out_dir / "merge-out"),
                "--minimal",
            ]
        )

    def test_summarise_whole_performance_csv(self):
        main(
            [
                "stat_visualization",
                "summarise_whole_performance_csv",
                "--dir",
                str(data_dir),
                "--output",
                str(out_dir / "summarise_whole_performance_csv-out.csv"),
            ]
        )

    def test_write_linegraph_per_user(self):
        main(
            [
                "stat_visualization",
                "write_linegraph_per_user",
                "--csv",
                str(data_dir / "visualization-dir/タスクlist.csv"),
                "--output_dir",
                str(out_dir / "write_linegraph_per_user-out"),
                "--minimal",
            ]
        )

    def test_write_performance_scatter_per_user(self):
        main(
            [
                "stat_visualization",
                "write_performance_scatter_per_user",
                "--csv",
                str(data_dir / "visualization-dir/メンバごとの生産性と品質.csv"),
                "--output_dir",
                str(out_dir / "write_performance_scatter_per_user-out"),
            ]
        )

    def test_write_performance_rating_csv(self):
        main(
            [
                "stat_visualization",
                "write_performance_rating_csv",
                "--dir",
                str(data_dir),
                "--output_dir",
                str(out_dir / "write_performance_rating_csv-out"),
            ]
        )

    def test_write_task_histogram(self):
        main(
            [
                "stat_visualization",
                "write_task_histogram",
                "--csv",
                str(data_dir / "visualization-dir/タスクlist.csv"),
                "--output_dir",
                str(out_dir / "write_task_histogram-out"),
                "--minimal",
            ]
        )

    def test_write_whole_linegraph(self):
        main(
            [
                "stat_visualization",
                "write_whole_linegraph",
                "--csv",
                str(data_dir / "visualization-dir/日毎の生産量と生産性.csv"),
                "--output_dir",
                str(out_dir / "write_whole_linegraph-out"),
            ]
        )
