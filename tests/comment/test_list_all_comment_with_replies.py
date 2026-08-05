from annofabcli.comment.utils import create_comment_list_with_replies


def create_comment(comment_id: str, *, node_type: str, comment: str, datetime_for_sorting: str, root_comment_id: str | None = None) -> dict:
    comment_node = {"_type": node_type}
    if root_comment_id is not None:
        comment_node["root_comment_id"] = root_comment_id

    return {
        "project_id": "project1",
        "task_id": "task1",
        "input_data_id": "input_data1",
        "comment_id": comment_id,
        "comment": comment,
        "comment_node": comment_node,
        "datetime_for_sorting": datetime_for_sorting,
        "reply_count": 0,
    }


def test_create_comment_list_with_replies():
    root_comment1 = create_comment(
        "root1",
        node_type="Root",
        comment="枠がずれています",
        datetime_for_sorting="2026-08-04T10:00:00+09:00",
    )
    root_comment2 = create_comment(
        "root2",
        node_type="Root",
        comment="ラベルが違います",
        datetime_for_sorting="2026-08-04T11:00:00+09:00",
    )
    reply_comment1 = create_comment(
        "reply1",
        node_type="Reply",
        comment="修正しました",
        datetime_for_sorting="2026-08-04T10:20:00+09:00",
        root_comment_id="root1",
    )
    reply_comment2 = create_comment(
        "reply2",
        node_type="Reply",
        comment="確認しました",
        datetime_for_sorting="2026-08-04T10:30:00+09:00",
        root_comment_id="root1",
    )

    actual = create_comment_list_with_replies([reply_comment2, root_comment2, reply_comment1, root_comment1])

    assert [e["comment_id"] for e in actual] == ["root1", "root2"]
    assert actual[0]["comment"] == "枠がずれています"
    assert [e["comment_id"] for e in actual[0]["reply_comments"]] == ["reply1", "reply2"]
    assert "reply_count" not in actual[0]["reply_comments"][0]
    assert actual[1]["reply_comments"] == []


def test_create_comment_list_with_replies__skip_orphan_reply_comment(caplog):
    root_comment = create_comment(
        "root1",
        node_type="Root",
        comment="枠がずれています",
        datetime_for_sorting="2026-08-04T10:00:00+09:00",
    )
    reply_comment = create_comment(
        "reply1",
        node_type="Reply",
        comment="修正しました",
        datetime_for_sorting="2026-08-04T10:20:00+09:00",
        root_comment_id="missing-root",
    )

    actual = create_comment_list_with_replies([reply_comment, root_comment])

    assert [e["comment_id"] for e in actual] == ["root1"]
    assert actual[0]["reply_comments"] == []
    assert "返信先のルートコメントが存在しないため" in caplog.text
