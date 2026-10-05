import io
import json
from pathlib import Path
from unittest.mock import Mock

import numpy
import pytest
from annofabapi.parser import lazy_parse_simple_annotation_dir_by_task
from annofabapi.segmentation import write_binary_image

from annofabcli.annotation.merge_segmentation import MergeSegmentationMain, merge_binary_image_array
from annofabcli.annotation.restore_annotation import RestoreAnnotationMain


def test_merge_binary_image_array_basic():
    # 基本的な動作確認
    input_array1 = numpy.array([[False, True], [True, False]], dtype=bool)
    input_array2 = numpy.array([[True, False], [False, True]], dtype=bool)
    expected_output = numpy.array([[True, True], [True, True]], dtype=bool)
    actual_output = merge_binary_image_array([input_array1, input_array2])
    numpy.testing.assert_array_equal(actual_output, expected_output)


def test_merge_binary_image_array_error_handling():
    # エラーハンドリングの確認
    with pytest.raises(ValueError):
        merge_binary_image_array([])


def test_merge_binary_image_array_boundary():
    # 境界値テスト
    input_array1 = numpy.array([], dtype=bool)
    input_array2 = numpy.array([], dtype=bool)
    expected_output = numpy.array([], dtype=bool)
    actual_output = merge_binary_image_array([input_array1, input_array2])
    numpy.testing.assert_array_equal(actual_output, expected_output)


@pytest.fixture
def segmentation_annotation(tmp_path):
    service = Mock()
    service.api.get_my_member_in_project.return_value = ({"member_role": "owner"}, None)
    images = {}
    details = []
    for index, pixels in enumerate([[[True, False], [True, True]], [[False, True], [True, False]]]):
        annotation_id = f"a{index + 1}"
        image_path = tmp_path / f"{annotation_id}.png"
        write_binary_image(numpy.array(pixels, dtype=bool), image_path)
        url = f"https://example.com/{annotation_id}"
        images[url] = image_path.read_bytes()
        details.append(
            {
                "annotation_id": annotation_id,
                "label_id": "label1",
                "attributes": [{"attribute_id": "attr1", "value": f"value{index}"}],
                "body": {"_type": "Outer", "url": url},
            }
        )
    annotation = {
        "project_id": "prj1",
        "task_id": "task1",
        "input_data_id": "input1",
        "updated_datetime": "2026-01-01T00:00:00Z",
        "format_version": "2.0.0",
        "details": details,
    }

    def get_image(url, *, stream):
        assert stream
        return Mock(raw=io.BytesIO(images[url]))

    def download_image(url, output_path):
        output_path.write_bytes(images[url])

    service.wrapper.execute_http_get.side_effect = get_image
    service.wrapper.download.side_effect = download_image
    service.wrapper.upload_data_to_s3.return_value = "uploaded/image.png"
    return service, annotation, images


def create_main_obj(service: Mock, backup_dir: Path | None) -> MergeSegmentationMain:
    return MergeSegmentationMain(
        service,
        project_id="prj1",
        label_ids=["label1"],
        label_names=["road"],
        all_yes=True,
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
        backup_dir=backup_dir,
    )


@pytest.mark.parametrize("with_backup", [True, False])
def test_update_segmentation_backup(tmp_path, segmentation_annotation, with_backup):
    service, annotation, images = segmentation_annotation
    backup_dir = tmp_path / "backup"
    main_obj = create_main_obj(service, backup_dir if with_backup else None)

    def put_annotation(*_args, **_kwargs):
        # 更新APIの呼び出し時点で、JSONと画像が保存されていることを確認する。
        if with_backup:
            assert json.loads((backup_dir / "task1/input1.json").read_text()) == annotation
            for detail in annotation["details"]:
                assert (backup_dir / "task1/input1" / detail["annotation_id"]).read_bytes() == images[detail["body"]["url"]]
        else:
            assert not backup_dir.exists()

    service.api.put_annotation.side_effect = put_annotation
    assert main_obj.merge_segmentation_annotation("task1", "input1", annotation)
    service.api.put_annotation.assert_called_once()

    if with_backup:
        # 保存したJSONと画像を既存のrestore処理で読み込み、元のアノテーションを復元できる。
        restored_images = []

        def upload_image(project_id, data, *, content_type):
            assert project_id == "prj1"
            assert content_type == "application/octet-stream"
            restored_images.append(data.read())
            return "restored/image.png"

        service.wrapper.upload_data_to_s3.side_effect = upload_image
        restore_obj = RestoreAnnotationMain(
            service,
            project_id="prj1",
            all_yes=True,
            include_complete_task=False,
            include_break_task=False,
            include_on_hold_task=False,
        )
        task_parser = next(lazy_parse_simple_annotation_dir_by_task(backup_dir))
        parser = next(task_parser.lazy_parse())
        request = restore_obj.editor_annotation_to_request_body_v2(parser.load_json(), parser)
        assert restored_images == list(images.values())
        assert [detail["annotation_id"] for detail in request["details"]] == ["a1", "a2"]
        assert [detail["attributes"] for detail in request["details"]] == [detail["attributes"] for detail in annotation["details"]]


def test_backup_failure_prevents_annotation_update(tmp_path, segmentation_annotation):
    service, annotation, _ = segmentation_annotation
    service.wrapper.download.side_effect = OSError("画像の保存に失敗")
    main_obj = create_main_obj(service, tmp_path / "backup")

    with pytest.raises(OSError):
        main_obj.merge_segmentation_annotation("task1", "input1", annotation)

    service.api.put_annotation.assert_not_called()
    service.wrapper.upload_data_to_s3.assert_not_called()


def test_no_changes_skip_backup(tmp_path, segmentation_annotation):
    service, annotation, _ = segmentation_annotation
    annotation["details"] = annotation["details"][:1]
    backup_dir = tmp_path / "backup"
    main_obj = create_main_obj(service, backup_dir)

    assert not main_obj.merge_segmentation_annotation("task1", "input1", annotation)
    assert not backup_dir.exists()
    service.wrapper.download.assert_not_called()
    service.api.put_annotation.assert_not_called()


def test_update_failure_preserves_backup(tmp_path, segmentation_annotation):
    service, annotation, images = segmentation_annotation
    service.api.put_annotation.side_effect = RuntimeError("更新に失敗")
    backup_dir = tmp_path / "backup"
    main_obj = create_main_obj(service, backup_dir)

    with pytest.raises(RuntimeError):
        main_obj.merge_segmentation_annotation("task1", "input1", annotation)

    assert json.loads((backup_dir / "task1/input1.json").read_text()) == annotation
    for detail in annotation["details"]:
        assert (backup_dir / "task1/input1" / detail["annotation_id"]).read_bytes() == images[detail["body"]["url"]]
