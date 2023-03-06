import pytest

from annofabcli.annotation.copy_annotation import CopyTargetByInputData, CopyTargetByTask, parse_copy_target


class TestCopyAnnotation:
    def test_parse_copy_target__by_task(self):
        actual = parse_copy_target("task1:task2")
        assert isinstance(actual, CopyTargetByTask)
        assert actual.src_task_id == "task1"
        assert actual.dest_task_id == "task2"

    def test_parse_copy_target__by_input_data(self):
        actual = parse_copy_target("task1/input5:task2/input6")
        assert isinstance(actual, CopyTargetByInputData)
        assert actual.src_task_id == "task1"
        assert actual.src_input_data_id == "input5"
        assert actual.dest_task_id == "task2"
        assert actual.dest_input_data_id == "input6"

    def test_parse_copy_target__not_supported(self):
        with pytest.raises(ValueError):
            parse_copy_target("task1/input5:task2")

        with pytest.raises(ValueError):
            parse_copy_target("task1:task2/input6")

        with pytest.raises(ValueError):
            parse_copy_target("task1:task2:task3")

        with pytest.raises(ValueError):
            parse_copy_target("task1")
