import os
from pathlib import Path

import pytest

from annofabcli.annotation.copy_annotation import CopyTargetByInputData, CopyTargetByTask, parse_copy_target

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

data_dir = Path("./tests/data/annotation")
out_dir = Path("./tests/out/annotation")
out_dir.mkdir(exist_ok=True, parents=True)


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

    def test_parse_copy_target__not_supported1(self):
        with pytest.raises(ValueError):
            parse_copy_target("task1/input5:task2")

    # TODO
    # ValueErrorのテストケースを追加する
