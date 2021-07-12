import os
from pathlib import Path

import pandas

from annofabcli.__main__ import main
from annofabcli.common.utils import read_multiheader_csv
from annofabcli.filesystem.mask_user_info import create_masked_name, create_masked_user_info_df

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

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

    def test_write_annotation_image(self):
        zip_path = data_dir / "simple-annotation.zip"
        label_color_file = data_dir / "label_color.json"
        output_image_dir = out_dir / "annotation-image"

        main(
            [
                "filesystem",
                "write_annotation_image",
                "--annotation",
                str(zip_path),
                "--output_dir",
                str(output_image_dir),
                "--image_size",
                "64x64",
                "--label_color",
                f"file://{str(label_color_file)}",
                "--image_extension",
                "jpg",
            ]
        )

    def test_filter_annotation(self):
        zip_path = data_dir / "simple-annotation.zip"
        output_dir = out_dir / "filter-annotation-output"

        main(
            [
                "filesystem",
                "filter_annotation",
                "--annotation",
                str(zip_path),
                "--output_dir",
                str(output_dir),
                "--task_query",
                '{"status":"complete"}',
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


class TestMaskUserInfo:
    def test_create_masked_name(self):
        assert create_masked_name("abc") == "P"

    def test_create_masked_user_info_df(self):
        # ヘッダ２行のCSVを読み込む
        df = create_masked_user_info_df(read_multiheader_csv(data_dir / "user2.csv", header_row_count=2))
        print(df)

        df = create_masked_user_info_df(
            read_multiheader_csv(data_dir / "user2.csv", header_row_count=2),
            not_masked_biography_set={"China"},
            not_masked_user_id_set=None,
        )
        print(df)

        df = create_masked_user_info_df(
            read_multiheader_csv(data_dir / "user2.csv", header_row_count=2),
            not_masked_biography_set=None,
            not_masked_user_id_set={"alice"},
        )
        print(df)

        df = create_masked_user_info_df(
            read_multiheader_csv(data_dir / "user2.csv", header_row_count=2),
            not_masked_biography_set={"China"},
            not_masked_user_id_set={"chris"},
        )
        print(df)

    def test_create_masked_user_info_df2(self):
        # ヘッダ２行のCSVを読み込む。ただし username, biography, account_id がないCSV
        df = create_masked_user_info_df(
            read_multiheader_csv(data_dir / "user2_1.csv", header_row_count=2),
            not_masked_biography_set={"China"},
            not_masked_user_id_set={"chris"},
        )
        print(df)

    def test_create_masked_user_info_df3(self):
        # ヘッダ1行のCSVを読み込む
        df = create_masked_user_info_df(pandas.read_csv(str(data_dir / "user1.csv")))
        print(df)
