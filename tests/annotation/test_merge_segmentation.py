from unittest.mock import Mock

import numpy
import pytest
from annofabapi.models import ProjectMemberRole, TaskStatus

from annofabcli.annotation.merge_segmentation import MergeSegmentationMain, merge_binary_image_array


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


def test_merge_segmentation_annotation_for_task__別担当のチェッカーは担当者変更オプションなしではスキップする():
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
    obj = MergeSegmentationMain(
        service,
        project_id="prj1",
        label_ids=["label1"],
        label_names=["label"],
        all_yes=True,
        change_operator_to_me=False,
        include_complete_task=False,
        include_break_task=False,
        include_on_hold_task=False,
    )
    obj.confirm_processing = Mock(return_value=True)  # type: ignore[method-assign]

    actual = obj.merge_segmentation_annotation_for_task("task1")

    assert actual == 0
    obj.confirm_processing.assert_not_called()
