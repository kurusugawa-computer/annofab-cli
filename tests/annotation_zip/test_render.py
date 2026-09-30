from pathlib import Path

import pytest

from annofabcli.__main__ import main
from annofabcli.annotation_zip.render import create_label_color_dict, read_input_data_id_csv

data_dir = Path("./tests/data/filesystem")
out_dir = Path("./tests/out/annotation_zip")


def test_read_input_data_id_csv() -> None:
    actual = read_input_data_id_csv(data_dir / "input_data_id_with_header.csv")

    assert actual == {"c6e1c2ec-6c7c-41c6-9639-4244c2ed2839": "lenna.png"}


def test_read_input_data_id_csv_preserves_leading_zeroes(tmp_path: Path) -> None:
    csv_path = tmp_path / "input_data.csv"
    csv_path.write_text("input_data_id,image_path\n001,image.png\n")

    actual = read_input_data_id_csv(csv_path)

    assert actual == {"001": "image.png"}


def test_create_label_color_dict() -> None:
    label_list = [
        {
            "label_id": "car_id",
            "label_name_en": "car",
            "label_name_ja": "車",
            "annotation_type": "bounding_box",
            "color": "#123456",
        },
        {
            "label_id": "bike_id",
            "label_name_en": "bike",
            "color": "#ABCDEF",
        },
    ]

    actual = create_label_color_dict(label_list)

    assert actual == {"car": "#123456", "bike": "#ABCDEF"}


@pytest.mark.parametrize(
    "label_list",
    [
        {"car": "#123456"},
        ["car"],
        [{"label_name_en": "car"}],
        [{"label_name_en": "car", "color": [18, 52, 86]}],
        [{"label_name_en": "", "color": "#123456"}],
        [
            {"label_name_en": "car", "color": "#123456"},
            {"label_name_en": "car", "color": "#ABCDEF"},
        ],
    ],
)
def test_create_label_color_dict__invalid(label_list: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        create_label_color_dict(label_list)


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
                "--label_color",
                '[{"label_id":"cat_id","label_name_en":"Cat","color":"#123456"}]',
            ]
        )

        assert (output_dir / "sample_1/c6e1c2ec-6c7c-41c6-9639-4244c2ed2839.png").exists()
