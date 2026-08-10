from unittest.mock import Mock

import numpy as np
from annofabapi.models import ProjectMemberRole, TaskStatus

from annofabcli.annotation.remove_segmentation_overlap import RemoveSegmentationOverlapMain, remove_overlap_of_binary_image_array


def test_remove_overlap_of_binary_image_array():
    # テスト用の入力データ
    binary_image_array_by_annotation = {
        "a1": np.array([[True, False], [True, True]]),
        "a2": np.array([[False, True], [True, False]]),
    }

    expected_output1 = {"a1": np.array([[True, False], [False, True]]), "a2": np.array([[False, True], [True, False]])}
    actual_output1 = remove_overlap_of_binary_image_array(binary_image_array_by_annotation, ["a1", "a2"])
    for annotation_id in ["a1", "a2"]:
        np.testing.assert_array_equal(actual_output1[annotation_id], expected_output1[annotation_id])

    expected_output2 = {"a1": np.array([[True, False], [True, True]]), "a2": np.array([[False, True], [False, False]])}
    actual_output2 = remove_overlap_of_binary_image_array(binary_image_array_by_annotation, ["a2", "a1"])
    for annotation_id in ["a1", "a2"]:
        np.testing.assert_array_equal(actual_output2[annotation_id], expected_output2[annotation_id])


def test_update_segmentation_annotation_for_task__別担当のチェッカーは担当者変更オプションなしではスキップする():
    service = Mock()
    service.api.account_id = "account_id"
    service.api.get_my_member_in_project.return_value = ({"member_role": ProjectMemberRole.ACCEPTER.value}, None)
    service.wrapper.get_task_or_none.return_value = {
        "task_id": "task1",
        "phase": "annotation",
        "status": TaskStatus.NOT_STARTED.value,
        "account_id": "other_account_id",
        "updated_datetime": "2026-08-10T00:00:00+09:00",
        "input_data_id_list": [],
    }
    obj = RemoveSegmentationOverlapMain(
        service,
        project_id="prj1",
        all_yes=True,
        change_operator_to_me=False,
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
    )
    obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]

    actual = obj.update_segmentation_annotation_for_task("task1")

    assert actual == 0
    obj.confirm_processing.assert_not_called()
