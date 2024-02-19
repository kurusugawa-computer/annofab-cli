from pathlib import Path

from annofabcli.__main__ import main

data_dir = Path("./tests/data/stat_visualization")
out_dir = Path("./tests/out/stat_visualization")


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

    def test__summarize_whole_performance_csv(self):
        main(
            [
                "stat_visualization",
                "summarize_whole_performance_csv",
                "--dir",
                str(data_dir / "summarize_whole_performance_csv"),
                "--output",
                str(out_dir / "summarize_whole_performance_csv-out.csv"),
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
