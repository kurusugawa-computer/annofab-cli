from pathlib import Path

from annofabcli.__main__ import main

data_dir = Path("./tests/data/filesystem")
out_dir = Path("./tests/out/annotation_zip")


class TestCommandLine:
    def test_filter(self):
        zip_path = data_dir / "simple-annotation.zip"
        output_dir = out_dir / "filter-output"

        main(
            [
                "annotation_zip",
                "filter",
                "--annotation",
                str(zip_path),
                "--output_dir",
                str(output_dir),
                "--task_query",
                '{"status":"complete"}',
            ]
        )

        assert (output_dir / "sample_1/c6e1c2ec-6c7c-41c6-9639-4244c2ed2839.json").exists()

    def test_filter_dir_with_outer_file(self):
        annotation_dir = data_dir / "merge/annotation-A"
        output_dir = out_dir / "filter-dir-output"

        main(
            [
                "annotation_zip",
                "filter",
                "--annotation",
                str(annotation_dir),
                "--output_dir",
                str(output_dir),
                "--input_data_id",
                "input2",
            ]
        )

        assert (output_dir / "task2/input2/1e2931d2-de34-4956-ab75-81f710dc0108").exists()
