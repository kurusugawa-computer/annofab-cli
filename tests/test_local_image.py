import json
import os
import zipfile
from pathlib import Path

import pytest
from annofabapi.parser import SimpleAnnotationDirParser, SimpleAnnotationParser, SimpleAnnotationZipParser

from annofabcli.common.image import write_annotation_image, write_annotation_images_from_path

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

test_dir = Path("./tests/data")
out_dir = Path("./tests/out")

with (test_dir / "label_color.json").open(encoding="utf-8") as f:
    label_color_json = json.load(f)
    label_color_dict = {label_name: tuple(rgb) for label_name, rgb in label_color_json.items()}


def test_write_image():
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


def test_write_image_wihtout_outer_file():
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

    def test_write_annotation_images_from_path_2(self):
        zip_path = test_dir / "simple-annotation.zip"
        output_image_dir = out_dir / "annotation-image"

        input_data_json = test_dir / "input_data2.json"
        with input_data_json.open() as f:
            input_data_list = json.load(f)
            input_data_dict = {e["input_data_id"]: e for e in input_data_list}

        def is_target_parser_func(parser: SimpleAnnotationParser) -> bool:
            return parser.task_id == "sample_1"

        write_annotation_images_from_path(
            annotation_path=zip_path,
            image_size=(64, 64),
            label_color_dict=label_color_dict,
            output_dir_path=output_image_dir,
            input_data_dict=input_data_dict,
            metadata_key_of_image_width="width",
            metadata_key_of_image_height="height",
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

    def test_argument_validate_error_メタデータが引数に指定されていない(self):
        zip_path = test_dir / "simple-annotation.zip"
        output_image_dir = out_dir / "annotation-image"

        def is_target_parser_func(parser: SimpleAnnotationParser) -> bool:
            return parser.task_id == "sample_1"

        input_data_dict = {
            "c86205d1-bdd4-4110-ae46-194e661d622b": {
                "input_data_id": "c86205d1-bdd4-4110-ae46-194e661d622b",
                "metadata": {"width": "64", "height": "64"},
            }
        }

        with pytest.raises(ValueError):
            write_annotation_images_from_path(
                annotation_path=zip_path,
                label_color_dict=label_color_dict,
                output_dir_path=output_image_dir,
                input_data_dict=input_data_dict,
                is_target_parser_func=is_target_parser_func,
            )
