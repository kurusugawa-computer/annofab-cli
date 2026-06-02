from pathlib import Path

from annofabcli.__main__ import main

data_dir = Path("./tests/data/filesystem")
out_dir = Path("./tests/out/filesystem")


class TestCommandLine:
    def test_draw_annotation(self):
        zip_path = data_dir / "simple-annotation.zip"
        output_dir = out_dir / "draw-annotation-output"

        main(
            [
                "filesystem",
                "draw_annotation",
                "--annotation",
                str(zip_path),
                "--output_dir",
                str(output_dir),
                "--input_data_id_csv",
                str(data_dir / "input_data_id.csv"),
                "--image_dir",
                "tests/data",
            ]
        )

    def test_mask_user_info(self):
        csv_path = data_dir / "user1.csv"
        out_path = out_dir / "out-user1.csv"

        main(
            [
                "filesystem",
                "mask_user_info",
                "--csv",
                str(csv_path),
                "--output",
                str(out_path),
            ]
        )
