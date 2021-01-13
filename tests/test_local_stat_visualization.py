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
                str(data_dir / "visualization-dir"),
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
