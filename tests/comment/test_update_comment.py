import copy
import pickle
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from annofabapi.models import CommentType

from annofabcli.comment.put_comment import PutCommentMain
from annofabcli.comment.update_comment import convert_updated_comment_list, read_updated_comment_csv


@pytest.mark.parametrize("comment_type", [CommentType.INSPECTION, CommentType.ONHOLD])
@pytest.mark.parametrize(
    "changes",
    [
        {"comment": "変更後の本文"},
        {"comment": ""},
        {"annotation_id": None},
        {"annotation_id": "annotation2"},
        {"data": {"x": 1.4, "y": 2.6, "_type": "Point"}},
        {"phrases": []},
        {"phrases": None},
    ],
)
def test_update_preserves_unspecified_fields(comment_type: CommentType, changes: dict[str, object]) -> None:
    if comment_type == CommentType.ONHOLD and ("data" in changes or "phrases" in changes):
        pytest.skip("保留コメントには座標と定型指摘を指定できません")
    original: dict[str, Any] = {
        "comment_id": "comment1",
        "comment": "既存の本文",
        "comment_type": comment_type.value,
        "phase": "annotation",
        "phase_stage": 2,
        "account_id": "original_author",
        "phrases": ["phrase1"] if comment_type == CommentType.INSPECTION else [],
        "comment_node": {
            "_type": "Root",
            "status": "resolved",
            "data": {"x": 10, "y": 20, "_type": "Point"} if comment_type == CommentType.INSPECTION else None,
            "annotation_id": "annotation1",
            "label_id": "label1",
        },
    }
    old_comment = copy.deepcopy(original)
    service = Mock()
    service.api.account_id = "executor"
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    service.api.get_annotation_specs.return_value = ({"labels": []}, None)
    service.api.get_comments.return_value = ([old_comment], None)
    service.api.get_editor_annotation.return_value = ({"details": [{"annotation_id": "annotation2", "label_id": "label2"}]}, None)
    main = PutCommentMain(service, project_id="project1", comment_type=comment_type)
    comments = convert_updated_comment_list(
        [{"task_id": "task1", "input_data_id": "input1", "comment_id": "comment1", **changes}],
        comment_type=comment_type,
    )
    assert pickle.loads(pickle.dumps(comments)) == comments

    count = main.add_comments_to_working_task(
        {"task_id": "task1", "input_data_id_list": ["input1"], "phase": "inspection", "phase_stage": 1},
        comments["task1"],
        put_mode="update",
    )

    expected = copy.deepcopy(original)
    expected["_type"] = "Put"
    for key, value in changes.items():
        if key in {"comment", "phrases"}:
            expected[key] = value
        else:
            expected["comment_node"][key] = value
    if "annotation_id" in changes:
        expected["comment_node"]["label_id"] = "label2" if changes["annotation_id"] else None
    if "data" in changes:
        expected["comment_node"]["data"] = {"x": 1, "y": 3, "_type": "Point"}
    assert count == 1
    assert service.api.batch_update_comments.call_args.kwargs["request_body"] == [expected]
    assert old_comment == original


@pytest.mark.parametrize("comment_type", [CommentType.INSPECTION, CommentType.ONHOLD])
@pytest.mark.parametrize("node_type", ["Root", "Reply"])
@pytest.mark.parametrize("exists", [True, False])
def test_update_skips_missing_or_different_comment(comment_type: CommentType, node_type: str, *, exists: bool) -> None:
    service = Mock()
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    service.api.get_annotation_specs.return_value = ({"labels": []}, None)
    old_comments = [{"comment_id": "comment1", "comment_type": "other" if node_type == "Root" else comment_type.value, "comment_node": {"_type": node_type}}] if exists else []
    service.api.get_comments.return_value = (old_comments, None)
    main = PutCommentMain(service, project_id="project1", comment_type=comment_type)
    comments = convert_updated_comment_list(
        [{"task_id": "task1", "input_data_id": "input1", "comment_id": "comment1", "comment": "変更"}],
        comment_type=comment_type,
    )
    count = main.add_comments_to_working_task({"task_id": "task1", "input_data_id_list": ["input1"]}, comments["task1"], put_mode="update")
    assert count == 0
    service.api.batch_update_comments.assert_not_called()


def test_update_without_changes_skips_api_update() -> None:
    service = Mock()
    service.api.get_project.return_value = ({"input_data_type": "image"}, None)
    service.api.get_annotation_specs.return_value = ({"labels": []}, None)
    service.api.get_comments.return_value = ([{"comment_id": "comment1", "comment_type": "inspection", "comment_node": {"_type": "Root"}}], None)
    main = PutCommentMain(service, project_id="project1", comment_type=CommentType.INSPECTION)
    comments = convert_updated_comment_list([{"task_id": "task1", "input_data_id": "input1", "comment_id": "comment1"}], comment_type=CommentType.INSPECTION)
    assert main.add_comments_to_working_task({"task_id": "task1", "input_data_id_list": ["input1"]}, comments["task1"], put_mode="update") == 0
    service.api.batch_update_comments.assert_not_called()


@pytest.mark.parametrize("changes", [{"comment": None}, {"data": None}, {}])
def test_update_input_requires_valid_values_and_comment_id(changes: dict[str, object]) -> None:
    record = {"task_id": "task1", "input_data_id": "input1", **changes}
    if changes:
        record["comment_id"] = "comment1"
    with pytest.raises(ValueError):
        convert_updated_comment_list([record], comment_type=CommentType.INSPECTION)


@pytest.mark.parametrize("comment_type", [CommentType.INSPECTION, CommentType.ONHOLD])
def test_update_csv_preserves_missing_columns_and_empty_cells(tmp_path: Path, comment_type: CommentType) -> None:
    path = tmp_path / "comments.csv"
    path.write_text("task_id,input_data_id,comment_id,annotation_id\ntask1,input1,comment1,annotation2\ntask1,input1,comment2,\n", encoding="utf-8")
    comments = read_updated_comment_csv(path, comment_type=comment_type)
    assert comments["task1"]["input1"][0].model_dump(exclude_unset=True) == {"comment_id": "comment1", "annotation_id": "annotation2"}
    assert comments["task1"]["input1"][1].model_dump(exclude_unset=True) == {"comment_id": "comment2"}


def test_update_csv_accepts_data_without_comment(tmp_path: Path) -> None:
    path = tmp_path / "comments.csv"
    path.write_text('task_id,input_data_id,comment_id,data,phrases\ntask1,input1,comment1,"{""x"":10,""y"":20,""_type"":""Point""}",[]\n', encoding="utf-8")
    comments = read_updated_comment_csv(path, comment_type=CommentType.INSPECTION)
    assert comments["task1"]["input1"][0].model_dump(exclude_unset=True) == {
        "comment_id": "comment1",
        "data": {"x": 10, "y": 20, "_type": "Point"},
        "phrases": [],
    }
