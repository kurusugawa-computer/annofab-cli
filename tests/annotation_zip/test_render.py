from pathlib import Path

from annofabcli.__main__ import main
from annofabcli.annotation_zip.render import read_input_data_id_csv

data_dir = Path("./tests/data/filesystem")
out_dir = Path("./tests/out/annotation_zip")


def test_read_input_data_id_csv():
    actual = read_input_data_id_csv(data_dir / "input_data_id_with_header.csv")

    assert actual == {"c6e1c2ec-6c7c-41c6-9639-4244c2ed2839": "lenna.png"}


class TestCommandLine:
    def test_render(self):
        zip_path = data_dir / "simple-annotation.zip"
        output_dir = out_dir / "render-output"

        main(
            [
                "annotation_zip",
                "render",
                "--annotation",
                str(zip_path),
                "--output_dir",
                str(output_dir),
                "--input_data_id_csv",
                str(data_dir / "input_data_id_with_header.csv"),
                "--image_dir",
                "tests/data",
            ]
        )

        assert (output_dir / "sample_1/c6e1c2ec-6c7c-41c6-9639-4244c2ed2839.png").exists()

    def test_render_with_image_size(self):
        zip_path = data_dir / "simple-annotation.zip"
        output_dir = out_dir / "render-with-image-size-output"

        main(
            [
                "annotation_zip",
                "render",
                "--annotation",
                str(zip_path),
                "--output_dir",
                str(output_dir),
                "--image_size",
                "1280x720",
            ]
        )

        assert (output_dir / "sample_1/c6e1c2ec-6c7c-41c6-9639-4244c2ed2839.png").exists()
