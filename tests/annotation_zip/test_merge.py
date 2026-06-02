import json
import shutil
from pathlib import Path

from annofabcli.__main__ import main

data_dir = Path("./tests/data/filesystem")
out_dir = Path("./tests/out/annotation_zip")


class TestCommandLine:
    def test_merge_with_task_id(self):
        annotation_dir1 = data_dir / "merge/annotation-A"
        annotation_dir2 = data_dir / "merge/annotation-B"
        output_dir = out_dir / "merge-output1"
        shutil.rmtree(output_dir, ignore_errors=True)

        main(
            [
                "annotation_zip",
                "merge",
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

        assert (output_dir / "task1/input1.json").exists()
        assert (output_dir / "task2/input2.json").exists()
        assert not (output_dir / "task3/input2.json").exists()

    def test_merge_zip_and_dir(self):
        annotation_dir2 = data_dir / "merge/annotation-B"
        annotation_zip1 = data_dir / "merge/annotation-A.zip"
        output_dir1 = out_dir / "merge-output21"
        output_dir2 = out_dir / "merge-output22"
        shutil.rmtree(output_dir1, ignore_errors=True)
        shutil.rmtree(output_dir2, ignore_errors=True)

        main(
            [
                "annotation_zip",
                "merge",
                "--annotation",
                str(annotation_zip1),
                str(annotation_dir2),
                "--output_dir",
                str(output_dir1),
            ]
        )

        main(
            [
                "annotation_zip",
                "merge",
                "--annotation",
                str(annotation_dir2),
                str(annotation_zip1),
                "--output_dir",
                str(output_dir2),
            ]
        )

        with (output_dir1 / "task1/input1.json").open(encoding="utf-8") as f:
            merged_annotation = json.load(f)

        merged_annotation_by_id = {e["annotation_id"]: e for e in merged_annotation["details"]}
        assert merged_annotation_by_id["anno2"]["data"]["right_bottom"] == {"x": 120, "y": 120}
        assert (output_dir1 / "task3/input2.json").exists()
        assert (output_dir2 / "task2/input2.json").exists()
