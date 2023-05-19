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

    def test_merge_annotation1(self):
        annotation_dir1 = data_dir / "merge/annotation-A"
        annotation_dir2 = data_dir / "merge/annotation-B"
        output_dir = out_dir / "merge-annotation-output1"

        main(
            [
                "filesystem",
                "merge_annotation",
                "--annotation",
                str(annotation_dir1),
                str(annotation_dir2),
                "--output_dir",
                str(output_dir),
                "--task_id",
                "task1",
                "task2",
            ]
        )

    def test_merge_annotation2(self):
        annotation_dir2 = data_dir / "merge/annotation-B"
        annotation_zip1 = data_dir / "merge/annotation-A.zip"
        output_dir1 = out_dir / "merge-annotation-output21"
        output_dir2 = out_dir / "merge-annotation-output22"

        main(
            [
                "filesystem",
                "merge_annotation",
                "--annotation",
                str(annotation_zip1),
                str(annotation_dir2),
                "--output_dir",
                str(output_dir1),
            ]
        )

        main(
            [
                "filesystem",
                "merge_annotation",
                "--annotation",
                str(annotation_dir2),
                str(annotation_zip1),
                "--output_dir",
                str(output_dir2),
            ]
        )
