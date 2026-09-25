import argparse
import collections
from typing import Any

import pandas
from annofabapi.models import TaskPhase, TaskStatus

from annofabcli.annotation_zip.count_annotation import CountAnnotationMain, validate_with_per_input_data
from annofabcli.annotation_zip.task_metadata import add_task_metadata_to_dataframe, add_task_metadata_to_dict_list
from annofabcli.statistics.list_annotation_count import AnnotationCounterByTask


def test_to_label_count_dict():
    counter = AnnotationCounterByTask(
        project_id="project1",
        task_id="task1",
        task_status=TaskStatus.COMPLETE,
        task_phase=TaskPhase.ACCEPTANCE,
        task_phase_stage=1,
        input_data_count=2,
        annotation_count=3,
        annotation_count_by_label=collections.Counter({"dog": 2, "cat": 1}),
        annotation_count_by_attribute=collections.Counter({("dog", "occluded", "true"): 2}),
    )

    actual = CountAnnotationMain.to_label_count_dict(counter)

    assert actual["annotation_count"] == 3
    assert actual["annotation_count_by_label"] == {"dog": 2, "cat": 1}
    assert "annotation_count_by_attribute" not in actual


def test_to_attribute_value_count_dict():
    counter = AnnotationCounterByTask(
        project_id="project1",
        task_id="task1",
        task_status=TaskStatus.COMPLETE,
        task_phase=TaskPhase.ACCEPTANCE,
        task_phase_stage=1,
        input_data_count=2,
        annotation_count=3,
        annotation_count_by_label=collections.Counter({"dog": 2, "cat": 1}),
        annotation_count_by_attribute=collections.Counter({("dog", "occluded", "true"): 2}),
    )

    actual = CountAnnotationMain.to_attribute_value_count_dict(counter)

    assert "annotation_count" not in actual
    assert actual["annotation_count_by_attribute_value"] == {"dog": {"occluded": {"true": 2}}}
    assert "annotation_count_by_label" not in actual
    assert "annotation_count_by_attribute" not in actual


class TestValidateWithPerInputData:
    def test_group_byがtask_idでない場合はFalseを返す(self, capsys):
        args = argparse.Namespace(with_per_input_data=True, group_by="input_data_id", format="csv")

        actual = validate_with_per_input_data(args, "count_annotation_by_label")

        assert actual is False
        assert "`--group_by task_id`" in capsys.readouterr().err

    def test_formatがcsvでない場合はFalseを返す(self, capsys):
        args = argparse.Namespace(with_per_input_data=True, group_by="task_id", format="json")

        actual = validate_with_per_input_data(args, "count_annotation_by_attribute_value")

        assert actual is False
        assert "`--format csv`" in capsys.readouterr().err

    def test_with_per_input_dataがFalseの場合はTrueを返す(self):
        args = argparse.Namespace(with_per_input_data=False, group_by="input_data_id", format="json")

        assert validate_with_per_input_data(args, "count_annotation_by_label") is True


def test_add_task_metadata_to_dataframe_and_dict_list():
    task_metadata_by_task_id: dict[str, dict[str, Any]] = {
        "task1": {"customer": "A", "priority": 1},
        "task2": {"customer": "B"},
    }
    df = pandas.DataFrame([{"task_id": "task1", "annotation_id": "annotation1"}, {"task_id": "task2", "annotation_id": "annotation2"}])

    actual_df = add_task_metadata_to_dataframe(df, task_metadata_by_task_id)
    actual_dict_list = add_task_metadata_to_dict_list(df.to_dict(orient="records"), task_metadata_by_task_id)

    assert actual_df.columns.tolist() == ["task_id", "task_metadata.customer", "task_metadata.priority", "annotation_id"]
    assert actual_df.loc[0, "task_metadata.customer"] == "A"
    assert pandas.isna(actual_df.loc[1, "task_metadata.priority"])
    assert actual_dict_list[0]["task_metadata"] == {"customer": "A", "priority": 1}
    assert actual_dict_list[1]["task_metadata"] == {"customer": "B"}
