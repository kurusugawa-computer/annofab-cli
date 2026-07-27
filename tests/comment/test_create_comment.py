from pathlib import Path

from annofabcli.comment.put_comment import (
    convert_cli_inspection_comment_list,
    convert_cli_onhold_comment_list,
    read_inspection_comment_csv,
    read_onhold_comment_csv,
)


def test_convert_cli_inspection_comment_list() -> None:
    comments = convert_cli_inspection_comment_list(
        [
            {
                "task_id": "task1",
                "input_data_id": "input1",
                "comment": "コメント1",
                "data": {"x": 10, "y": 20, "_type": "Point"},
                "annotation_id": "annotation1",
                "phrases": ["phrase1"],
                "comment_id": "comment1",
            }
        ]
    )

    comment = comments["task1"]["input1"][0]
    assert comment.comment == "コメント1"
    assert comment.data == {"x": 10, "y": 20, "_type": "Point"}
    assert comment.annotation_id == "annotation1"
    assert comment.phrases == ["phrase1"]
    assert comment.comment_id == "comment1"


def test_convert_cli_onhold_comment_list() -> None:
    comments = convert_cli_onhold_comment_list(
        [
            {
                "task_id": "task1",
                "input_data_id": "input1",
                "comment": "コメント1",
                "annotation_id": "annotation1",
                "comment_id": "comment1",
            }
        ]
    )

    comment = comments["task1"]["input1"][0]
    assert comment.comment == "コメント1"
    assert comment.annotation_id == "annotation1"
    assert comment.comment_id == "comment1"


def test_read_inspection_comment_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "inspection_comment.csv"
    csv_path.write_text('task_id,input_data_id,comment,data,annotation_id,phrases,comment_id\ntask1,input1,コメント1,"{""x"":10,""y"":20,""_type"":""Point""}",annotation1,"[""phrase1""]",comment1')

    comments = read_inspection_comment_csv(csv_path)

    comment = comments["task1"]["input1"][0]
    assert comment.comment == "コメント1"
    assert comment.data == {"x": 10, "y": 20, "_type": "Point"}
    assert comment.annotation_id == "annotation1"
    assert comment.phrases == ["phrase1"]
    assert comment.comment_id == "comment1"


def test_read_onhold_comment_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "onhold_comment.csv"
    csv_path.write_text("task_id,input_data_id,comment,annotation_id,comment_id\ntask1,input1,コメント1,annotation1,comment1")

    comments = read_onhold_comment_csv(csv_path)

    comment = comments["task1"]["input1"][0]
    assert comment.comment == "コメント1"
    assert comment.annotation_id == "annotation1"
    assert comment.comment_id == "comment1"
