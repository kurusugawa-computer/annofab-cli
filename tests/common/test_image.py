import zipfile
from pathlib import Path

import numpy
import PIL
import pytest
from annofabapi.parser import SimpleAnnotationDirParser, SimpleAnnotationParser, SimpleAnnotationZipParser

from annofabcli.common.image import (
    write_annotation_grayscale_image,
    write_annotation_image,
    write_annotation_images_from_path,
)

test_dir = Path("./tests/data")
out_dir = Path("./tests/out")

label_color_dict = {
    "Cat": (255, 99, 71),
    "leg": (27, 144, 185),
    "eye": (88, 113, 249),
    "dog": (188, 83, 41),
    "human": (210, 54, 28),
    "bird": (29, 202, 101),
    "climatic": (255, 255, 255),
}


def test_write_annotation_image():
    zip_path = test_dir / "simple-annotation.zip"
    output_image_file = out_dir / "annotation.png"

    with zipfile.ZipFile(zip_path) as zip_file:
        parser = SimpleAnnotationZipParser(zip_file, "sample_1/c6e1c2ec-6c7c-41c6-9639-4244c2ed2839.json")

        write_annotation_image(
            parser=parser,
            image_size=(64, 64),
            label_color_dict=label_color_dict,
            output_image_file=output_image_file,
            background_color=(64, 64, 64),
        )


def test_write_annotation_image__wihtout_outer_file():
    output_image_file = out_dir / "annotation_without_painting.png"

    # 外部ファイルが見つからない状態で画像を生成する。
    parser = SimpleAnnotationDirParser(test_dir / "simple-annotation.json")
    write_annotation_image(
        parser=parser,
        image_size=(64, 64),
        label_color_dict=label_color_dict,
        output_image_file=output_image_file,
        background_color=(64, 64, 64),
    )


class Test__write_annotation_grayscale_image:
    def test_ok(self):
        zip_path = test_dir / "simple-annotation.zip"
        output_image_file = out_dir / "annotation_grayscale.png"

        with zipfile.ZipFile(zip_path) as zip_file:
            parser = SimpleAnnotationZipParser(zip_file, "sample_1/c6e1c2ec-6c7c-41c6-9639-4244c2ed2839.json")

            write_annotation_grayscale_image(
                parser=parser,
                image_size=(64, 64),
                output_image_file=output_image_file,
            )

        data = numpy.array(PIL.Image.open(output_image_file).convert("L"))
        assert data.min() == 0
        assert data.max() == 5


class Test_write_annotation_images_from_path:
    def test_write_annotation_images_from_path(self):
        zip_path = test_dir / "simple-annotation.zip"
        output_image_dir = out_dir / "annotation-image"

        def is_target_parser_func(parser: SimpleAnnotationParser) -> bool:
            return parser.task_id == "sample_1"

        write_annotation_images_from_path(
            annotation_path=zip_path,
            image_size=(64, 64),
            label_color_dict=label_color_dict,
            output_dir_path=output_image_dir,
            background_color=(64, 64, 64),
            is_target_parser_func=is_target_parser_func,
        )

    def test_write_annotation_images_from_path_3(self):
        # 入力データのsystem_metadataから画像サイズを参照
        zip_path = test_dir / "simple-annotation.zip"
        output_image_dir = out_dir / "annotation-image"

        def is_target_parser_func(parser: SimpleAnnotationParser) -> bool:
            return parser.task_id == "sample_1"

        input_data_dict = {
            "c86205d1-bdd4-4110-ae46-194e661d622b": {
                "input_data_id": "c86205d1-bdd4-4110-ae46-194e661d622b",
                "metadata": {"width": "64", "height": "64"},
                "system_metadata": {
                    "resized_resolution": None,
                    "original_resolution": {"width": 128, "height": 128},
                    "_type": "Image",
                },
            }
        }

        write_annotation_images_from_path(
            annotation_path=zip_path,
            label_color_dict=label_color_dict,
            output_dir_path=output_image_dir,
            input_data_dict=input_data_dict,
            is_target_parser_func=is_target_parser_func,
        )

    def test_argument_validate_error__image_size_or_input_data_dictが引数に指定されていない(self):
        zip_path = test_dir / "simple-annotation.zip"
        output_image_dir = out_dir / "annotation-image"

        def is_target_parser_func(parser: SimpleAnnotationParser) -> bool:
            return parser.task_id == "sample_1"

        with pytest.raises(ValueError):
            write_annotation_images_from_path(
                annotation_path=zip_path,
                label_color_dict=label_color_dict,
                output_dir_path=output_image_dir,
                background_color=(64, 64, 64),
                is_target_parser_func=is_target_parser_func,
            )
