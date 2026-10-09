from unittest.mock import Mock

import pytest
from annofabapi.plugin import EditorPluginId

from annofabcli.comment.create_inspection_comment_simply import CreateInspectionCommentSimply, add_parser


@pytest.mark.parametrize("configuration", [None, {}, {"plugin_id": "custom-editor"}])
@pytest.mark.parametrize("comment_data", [None, '{"_type": "Custom", "data": "{}"}'])
def test_unsupported_editor_stops_before_changing_tasks(configuration: dict | None, comment_data: str | None) -> None:
    service = Mock()
    service.api.get_project.return_value = ({"input_data_type": "custom", "configuration": configuration}, None)
    argv = ["--project_id", "project1", "--task_id", "task1", "--comment", "確認してください", "--yes"]
    if comment_data is not None:
        argv.extend(["--comment_data", comment_data])
    args = add_parser().parse_args(argv)

    with pytest.raises(SystemExit) as exc_info:
        CreateInspectionCommentSimply(service, Mock(), args).main()

    assert exc_info.value.code == 2
    service.wrapper.get_task_or_none.assert_not_called()
    service.wrapper.change_task_operator.assert_not_called()
    service.wrapper.change_task_status_to_working.assert_not_called()
    service.api.batch_update_comments.assert_not_called()


@pytest.mark.parametrize("input_data_type", ["image", "movie", "custom"])
def test_supported_project_creates_inspection_comment(input_data_type: str) -> None:
    service = Mock()
    service.api.account_id = "account1"
    service.api.get_project.return_value = ({"input_data_type": input_data_type, "configuration": {"plugin_id": EditorPluginId.THREE_DIMENSION.value}}, None)
    task = {"task_id": "task1", "phase": "inspection", "phase_stage": 1, "status": "not_started", "account_id": "account1", "input_data_id_list": ["input1"]}
    service.wrapper.get_task_or_none.return_value = task
    service.wrapper.change_task_status_to_working.return_value = {**task, "status": "working"}
    args = add_parser().parse_args(["--project_id", "project1", "--task_id", "task1", "--comment", "確認してください", "--yes"])

    CreateInspectionCommentSimply(service, Mock(), args).main()

    service.api.batch_update_comments.assert_called_once()
    data = service.api.batch_update_comments.call_args.kwargs["request_body"][0]["comment_node"]["data"]
    assert data["_type"] == {"image": "Point", "movie": "Time", "custom": "Custom"}[input_data_type]
