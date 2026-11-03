import argparse
from unittest.mock import Mock

from annofabcli.annotation.annotation_query import AnnotationQueryForAPI
from annofabcli.annotation.delete_annotation import DeleteAnnotation, DeleteAnnotationMain
from annofabcli.common.facade import AnnofabApiFacade


def test_task_deletion_command_uses_only_task_and_query_arguments():
    service = Mock()
    service.api.get_project.return_value = ({"title": "project"}, None)
    service.api.get_my_member_in_project.return_value = ({"member_role": "owner"}, None)
    service.wrapper.get_task_or_none.return_value = None
    args = argparse.Namespace(project_id="project1", task_id=["task1", "task2"], annotation_query=None, backup=None, include_complete_task=False, yes=True)

    DeleteAnnotation(service, AnnofabApiFacade(service), args).main()

    assert [call.args[1] for call in service.wrapper.get_task_or_none.call_args_list] == ["task1", "task2"]
    service.api.batch_update_annotations.assert_not_called()


def test_task_query_is_passed_to_annotation_search():
    service = Mock()
    service.wrapper.get_all_annotation_list.return_value = []
    command = DeleteAnnotationMain(service, "project1", include_complete_task=False, all_yes=True)

    command.get_annotation_list_for_task("task1", AnnotationQueryForAPI(label_id="label1"))

    query = service.wrapper.get_all_annotation_list.call_args.kwargs["query_params"]["query"]
    assert query["task_id"] == "task1"
    assert query["exact_match_task_id"] is True
    assert query["label_id"] == "label1"
