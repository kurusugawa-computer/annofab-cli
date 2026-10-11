import io
import json
import zipfile
from pathlib import Path

import numpy
import pytest
import yaml
from annofabapi.segmentation import write_binary_image
from PIL import Image

from annofabcli.__main__ import main
from annofabcli.annotation_zip.diff_annotation import format_diff_as_text
from annofabcli.annotation_zip.diff_compare import create_annotation_zip_diff
from annofabcli.common.exceptions import AnnofabCliException


def _detail(annotation_id="a1", *, label="car", data=None, attributes=None) -> dict:
    return {
        "annotation_id": annotation_id,
        "label": label,
        "data": data if data is not None else {"_type": "Point", "point": {"x": 10, "y": 20}},
        "attributes": attributes if attributes is not None else {"occluded": False, "type": "sedan"},
    }


def _source(tmp_path: Path, name, details, *, zipped=False, outer=None, metadata=None, input_path="task1/image1.json"):
    files = {input_path: json.dumps({"details": details, **(metadata or {})}).encode()}
    files.update(outer or {})
    if zipped:
        path = tmp_path / f"{name}.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for filename, content in files.items():
                archive.writestr(filename, content)
    else:
        path = tmp_path / name
        for filename, content in files.items():
            file = path / filename
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(content)
    return path


def _png(mask, *, compression=6) -> bytes:
    original = io.BytesIO()
    write_binary_image(mask, original)
    if compression == 6:
        return original.getvalue()
    result = io.BytesIO()
    with Image.open(io.BytesIO(original.getvalue())) as image:
        image.save(result, format="PNG", compress_level=compression)
    return result.getvalue()


@pytest.mark.parametrize(("left_zip", "right_zip"), [(False, False), (True, True), (False, True), (True, False)])
def test_ignore_metadata_and_order(tmp_path, left_zip, right_zip):
    left = _source(tmp_path, "left", [_detail(), _detail("a2")], zipped=left_zip, metadata={"task_id": "wrong", "updated_datetime": "old", "project_id": "p1"})
    right = _source(
        tmp_path,
        "right",
        [_detail("a2"), _detail(attributes={"type": "sedan", "occluded": False})],
        zipped=right_zip,
        metadata={"task_id": "other", "input_data_id": "other", "updated_datetime": "new", "project_id": "p2", "task_status": "complete", "input_data_name": "renamed"},
    )
    diff = create_annotation_zip_diff(left, right)
    assert not diff.has_diff
    assert format_diff_as_text(diff) == ""


def test_added_removed_and_fields(tmp_path):
    left = _source(tmp_path, "left", [_detail(), _detail("removed")])
    right = _source(tmp_path, "right", [_detail(label="bus", data={"_type": "Point", "point": {"x": 11, "y": 20}}, attributes={"occluded": True, "confidence": None}), _detail("added")])
    diff = create_annotation_zip_diff(left, right)
    assert diff.has_diff
    assert diff.annotations.added[0].annotation_id == "added"
    assert diff.annotations.removed[0].annotation_id == "removed"
    changed = diff.annotations.changed[0]
    assert (changed.task_id, changed.input_data_id, changed.annotation_id) == ("task1", "image1", "a1")
    assert changed.label_changed and changed.data_changed and changed.attributes_changed
    assert changed.added_attribute_keys == ["confidence"]
    assert changed.removed_attribute_keys == ["type"]
    assert changed.changed_attribute_keys == ["occluded"]
    text = yaml.safe_load(format_diff_as_text(diff).split("\n", 1)[1])
    assert text["changed"][0]["fields"] == ["label", "data", "attributes"]
    detail = yaml.safe_load(format_diff_as_text(diff, detail=True).split("\n", 1)[1])
    assert detail["changed"][0]["changes"]["label"] == {"left": "car", "right": "bus"}
    assert detail["changed"][0]["attributes"]["added"] == [{"key": "confidence", "right": None}]
    serialized = diff.model_dump()
    assert serialized["has_diff"]
    assert "changes" not in serialized["annotations"]["changed"][0]


def test_renamed_path_is_removal_and_addition(tmp_path):
    left = _source(tmp_path, "left", [_detail()])
    right = _source(tmp_path, "right", [_detail()], input_path="task2/image2.json")
    diff = create_annotation_zip_diff(left, right)
    assert not diff.annotations.changed
    assert diff.annotations.added[0].input_data_id == "image2"
    assert diff.annotations.removed[0].task_id == "task1"


def test_target_preserves_addition_and_removal(tmp_path):
    left = _source(tmp_path, "left", [_detail(), _detail("removed")])
    right = _source(tmp_path, "right", [_detail(data={"_type": "Classification"}), _detail("added")])
    diff = create_annotation_zip_diff(left, right, targets=["attributes"])
    assert not diff.annotations.changed
    assert diff.annotations.added and diff.annotations.removed


@pytest.mark.parametrize("attributes", [{}, {"type": None}, {"type": ""}])
def test_missing_null_and_empty_are_distinct(tmp_path, attributes):
    left = _source(tmp_path, "left", [_detail(attributes={"type": "sedan"})])
    right = _source(tmp_path, "right", [_detail(attributes=attributes)])
    assert create_annotation_zip_diff(left, right).annotations.changed[0].attributes_changed


@pytest.mark.parametrize(("left_value", "right_value"), [(True, 1), (False, 0), (1, True), (0, False), ({"flag": True}, {"flag": 1}), ([False], [0]), ([{"flag": True}], [{"flag": 1}])])
def test_boolean_and_number_attribute_values_are_distinct(tmp_path, left_value, right_value):
    left = _source(tmp_path, "left", [_detail(attributes={"value": left_value})])
    right = _source(tmp_path, "right", [_detail(attributes={"value": right_value})])
    changed = create_annotation_zip_diff(left, right).annotations.changed[0]
    assert changed.attributes_changed
    assert changed.changed_attribute_keys == ["value"]


def test_boolean_and_number_in_data_are_distinct(tmp_path):
    left = _source(tmp_path, "left", [_detail(data={"_type": "Unknown", "data": '{"kind":"CUBOID","metadata":{"flag":true}}'})])
    right = _source(tmp_path, "right", [_detail(data={"_type": "Unknown", "data": '{"kind":"CUBOID","metadata":{"flag":1}}'})])
    assert create_annotation_zip_diff(left, right).annotations.changed[0].data_changed


def test_equivalent_json_numbers_are_equal(tmp_path):
    left = _source(tmp_path, "left", [_detail(attributes={"value": 1}, data={"_type": "Point", "point": {"x": 10, "y": 20}})])
    right = _source(tmp_path, "right", [_detail(attributes={"value": 1.0}, data={"_type": "Point", "point": {"x": 10.0, "y": 20.0}})])
    assert not create_annotation_zip_diff(left, right).has_diff


def test_duplicate_annotation_id_is_error(tmp_path):
    left = _source(tmp_path, "left", [_detail(), _detail()])
    right = _source(tmp_path, "right", [_detail()])
    with pytest.raises(AnnofabCliException):
        create_annotation_zip_diff(left, right)


@pytest.mark.parametrize("targets", [("label", "data", "attributes"), ("label",)])
def test_image_wide_null_data_is_supported(tmp_path, targets):
    detail = {**_detail(), "data": None}
    left = _source(tmp_path, "left", [detail], zipped=True)
    right = _source(tmp_path, "right", [detail])
    assert not create_annotation_zip_diff(left, right, targets=targets).has_diff


def test_image_wide_null_data_change_is_reported(tmp_path):
    left = _source(tmp_path, "left", [{**_detail(), "data": None}])
    right = _source(tmp_path, "right", [_detail()])
    diff = create_annotation_zip_diff(left, right)
    assert diff.annotations.changed[0].data_changed
    detail = yaml.safe_load(format_diff_as_text(diff, detail=True).split("\n", 1)[1])
    assert detail["changed"][0]["changes"]["data"]["left"] is None


@pytest.mark.parametrize("zipped", [False, True])
@pytest.mark.parametrize("compression", [0, 6, 9])
def test_segmentation_same_mask_different_uri_or_encoding(tmp_path, zipped, compression):
    mask = numpy.eye(16, dtype=bool)
    left_bytes, right_bytes = _png(mask), _png(mask, compression=compression)
    if compression == 0:
        assert len(left_bytes) != len(right_bytes)
    left = _source(tmp_path, "left", [_detail(data={"_type": "Segmentation", "data_uri": "old.png"})], zipped=zipped, outer={"task1/image1/old.png": left_bytes})
    right = _source(tmp_path, "right", [_detail(data={"_type": "Segmentation", "data_uri": "new.png"})], zipped=not zipped, outer={"task1/image1/new.png": right_bytes})
    assert not create_annotation_zip_diff(left, right).has_diff


@pytest.mark.parametrize("different_shape", [False, True])
def test_segmentation_changed_mask(tmp_path, different_shape):
    left_mask = numpy.eye(8, dtype=bool)
    right_mask = numpy.eye(9, dtype=bool) if different_shape else numpy.fliplr(left_mask)
    left = _source(tmp_path, "left", [_detail(data={"_type": "SegmentationV2", "data_uri": "mask.png"})], outer={"task1/image1/mask.png": _png(left_mask)})
    right = _source(tmp_path, "right", [_detail(data={"_type": "SegmentationV2", "data_uri": "mask.png"})], zipped=True, outer={"task1/image1/mask.png": _png(right_mask)})
    changed = create_annotation_zip_diff(left, right).annotations.changed[0]
    assert changed.data_changed and changed.external_file_changed
    assert changed.external_file is not None
    assert changed.external_file["filled_pixel_count"] == {"left": 8, "right": 9 if different_shape else 8}
    assert changed.external_file["changed_pixel_count"] == (None if different_shape else 16)


def test_segmentation_same_file_size_different_mask(tmp_path):
    left_mask, right_mask = numpy.eye(8, dtype=bool), numpy.fliplr(numpy.eye(8, dtype=bool))
    left_bytes, right_bytes = _png(left_mask, compression=0), _png(right_mask, compression=0)
    assert len(left_bytes) == len(right_bytes)
    left = _source(tmp_path, "left", [_detail(data={"_type": "Segmentation", "data_uri": "mask.png"})], outer={"task1/image1/mask.png": left_bytes})
    right = _source(tmp_path, "right", [_detail(data={"_type": "Segmentation", "data_uri": "mask.png"})], outer={"task1/image1/mask.png": right_bytes})
    assert create_annotation_zip_diff(left, right).has_diff


@pytest.mark.parametrize("points", [[5, 1, 3], [1, 3, 5], [3, 5, 7]])
def test_segment_compares_sets_and_outputs_counts(tmp_path, points):
    left = _source(
        tmp_path, "left", [_detail(data={"_type": "Unknown", "data": "./image1/old"})], outer={"task1/image1/old": json.dumps({"kind": "SEGMENT", "version": "1", "points": [1, 3, 5]}).encode()}
    )
    right = _source(
        tmp_path,
        "right",
        [_detail(data={"_type": "Unknown", "data": "./image1/new"})],
        zipped=True,
        outer={"task1/image1/new": json.dumps({"points": points, "kind": "SEGMENT", "version": "1"}, indent=2).encode()},
    )
    diff = create_annotation_zip_diff(left, right)
    if points != [3, 5, 7]:
        assert not diff.has_diff
    else:
        assert diff.annotations.changed[0].external_file == {"kind": "SEGMENT", "point_count": {"left": 3, "right": 3}, "added_point_count": 1, "removed_point_count": 1}
        detail = yaml.safe_load(format_diff_as_text(diff, detail=True).split("\n", 1)[1])
        assert detail["changed"][0]["external_file"]["added_point_count"] == 1
        assert "points" not in json.dumps(diff.model_dump())
        assert "external_file:" not in format_diff_as_text(diff)


@pytest.mark.parametrize(
    "payload", [b"broken", b'{"kind":"SEGMENT","points":[true]}', b'{"kind":"SEGMENT","points":[-1]}', b'{"kind":"SEGMENT","version":"2","points":[]}', b'{"kind":"OTHER","points":[]}']
)
def test_invalid_segment_is_error(tmp_path, payload):
    data = {"_type": "Unknown", "data": "./image1/segment"}
    left = _source(tmp_path, "left", [_detail(data=data)], outer={"task1/image1/segment": payload})
    right = _source(tmp_path, "right", [_detail(data=data)], outer={"task1/image1/segment": payload})
    with pytest.raises(AnnofabCliException):
        create_annotation_zip_diff(left, right)


@pytest.mark.parametrize("outer", [{}, {"task1/image1/mask.png": b"not a PNG"}])
def test_missing_or_invalid_segmentation_is_error(tmp_path, outer):
    data = {"_type": "Segmentation", "data_uri": "mask.png"}
    left = _source(tmp_path, "left", [_detail(data=data)], outer=outer)
    right = _source(tmp_path, "right", [_detail(data=data)], outer={"task1/image1/mask.png": _png(numpy.eye(8, dtype=bool))})
    with pytest.raises(AnnofabCliException):
        create_annotation_zip_diff(left, right)
    assert not create_annotation_zip_diff(left, right, targets=["attributes"]).has_diff


@pytest.mark.parametrize("uri", ["../../outside.png", "/tmp/outside.png"])
def test_invalid_external_reference_is_error(tmp_path, uri):
    data = {"_type": "Segmentation", "data_uri": uri}
    left = _source(tmp_path, "left", [_detail(data=data)])
    right = _source(tmp_path, "right", [_detail(data=data)])
    with pytest.raises(AnnofabCliException):
        create_annotation_zip_diff(left, right)


def test_cli_local_without_login_and_empty_output(tmp_path, capsys):
    left = _source(tmp_path, "left", [_detail()])
    right = _source(tmp_path, "right", [_detail()])
    arguments = ["annotation_zip", "diff", "--left_annotation", str(left), "--right_annotation", str(right)]
    main([*arguments, "--format", "pretty_json"])
    assert json.loads(capsys.readouterr().out) == {"has_diff": False, "annotations": {"added": [], "removed": [], "changed": []}}
    output = tmp_path / "diff.txt"
    main([*arguments, "--output", str(output)])
    assert output.read_text() == ""


def test_cli_comparison_error_does_not_write_partial_output(tmp_path):
    left = _source(tmp_path, "left", [_detail(data={"_type": "Segmentation", "data_uri": "missing.png"})])
    right = _source(tmp_path, "right", [_detail(data={"_type": "Segmentation", "data_uri": "missing.png"})])
    output = tmp_path / "diff.json"
    with pytest.raises(SystemExit) as exc:
        main(["annotation_zip", "diff", "--left_annotation", str(left), "--right_annotation", str(right), "--output", str(output)])
    assert exc.value.code != 0
    assert not output.exists()
