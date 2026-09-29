import collections

from annofabapi.models import TaskPhase, TaskStatus

from annofabcli.annotation_zip.count_aggregation import aggregate_task_counts, needs_task_metadata, validate_group_by
from annofabcli.statistics.list_annotation_count import AnnotationCounterByTask


def create_task_count(
    task_id: str,
    *,
    task_phase: TaskPhase,
    task_status: TaskStatus,
    task_phase_stage: int = 1,
    input_data_count: int = 2,
    annotation_count: int = 3,
) -> AnnotationCounterByTask:
    return AnnotationCounterByTask(
        project_id="project1",
        task_id=task_id,
        task_status=task_status,
        task_phase=task_phase,
        task_phase_stage=task_phase_stage,
        input_data_count=input_data_count,
        annotation_count=annotation_count,
        annotation_count_by_label=collections.Counter({"car": annotation_count}),
        annotation_count_by_attribute=collections.Counter(),
    )


class TestValidateGroupBy:
    def test_サマリー項目は複数指定できる(self):
        assert validate_group_by(["task_phase", "task_status", "task_metadata.customer"]) is None

    def test_詳細項目と他の項目は同時に指定できない(self):
        assert validate_group_by(["input_data_id", "task_status"]) is not None
        assert validate_group_by(["task_id", "task_metadata.customer"]) is not None
        assert validate_group_by(["project_id", "task_status"]) is not None

    def test_不明な項目は指定できない(self):
        assert validate_group_by(["unknown"]) is not None

    def test_タスクメタデータが必要か判定できる(self):
        assert needs_task_metadata(["task_status", "task_metadata.customer"]) is True
        assert needs_task_metadata(["task_status"]) is False


def test_aggregate_task_counts_複数項目とメタデータで集計する():
    task_counts = [
        create_task_count("task1", task_phase=TaskPhase.ANNOTATION, task_status=TaskStatus.COMPLETE),
        create_task_count("task2", task_phase=TaskPhase.ANNOTATION, task_status=TaskStatus.COMPLETE, annotation_count=4),
        create_task_count("task3", task_phase=TaskPhase.INSPECTION, task_status=TaskStatus.BREAK),
    ]

    actual = aggregate_task_counts(
        task_counts,
        ["task_phase", "task_status", "task_metadata.customer"],
        value_counts_getter=lambda count: count.annotation_count_by_label,
        annotation_count_getter=lambda count: count.annotation_count,
        task_metadata_by_task_id={
            "task1": {"customer": "A"},
            "task2": {"customer": "A"},
            "task3": {},
        },
    )

    assert len(actual) == 2
    assert actual[0].group_values == {
        "task_phase": "annotation",
        "task_status": "complete",
        "task_metadata.customer": "A",
    }
    assert actual[0].task_count == 2
    assert actual[0].input_data_count == 4
    assert actual[0].annotation_count == 7
    assert actual[0].value_counts == {"car": 7}
    assert actual[1].group_values["task_metadata.customer"] is None


def test_aggregate_task_counts_辞書型のメタデータはJSON文字列として集計する():
    task_counts = [create_task_count("task1", task_phase=TaskPhase.ANNOTATION, task_status=TaskStatus.COMPLETE)]

    actual = aggregate_task_counts(
        task_counts,
        ["task_metadata.condition"],
        value_counts_getter=lambda count: count.annotation_count_by_label,
        task_metadata_by_task_id={"task1": {"condition": {"weather": "sunny", "hour": 10}}},
    )

    assert actual[0].group_values == {"task_metadata.condition": '{"hour":10,"weather":"sunny"}'}


def test_aggregate_task_counts_メタデータの真偽値と数値を別グループに集計する():
    metadata_values = [True, 1, 1.0, False, 0, 0.0]
    task_counts = [create_task_count(f"task{index}", task_phase=TaskPhase.ANNOTATION, task_status=TaskStatus.COMPLETE) for index in range(len(metadata_values))]

    actual = aggregate_task_counts(
        task_counts,
        ["task_metadata.value"],
        value_counts_getter=lambda count: count.annotation_count_by_label,
        task_metadata_by_task_id={f"task{index}": {"value": value} for index, value in enumerate(metadata_values)},
    )

    assert len(actual) == len(metadata_values)
    assert [(type(summary.group_values["task_metadata.value"]), summary.group_values["task_metadata.value"]) for summary in actual] == [
        (bool, True),
        (int, 1),
        (float, 1.0),
        (bool, False),
        (int, 0),
        (float, 0.0),
    ]
