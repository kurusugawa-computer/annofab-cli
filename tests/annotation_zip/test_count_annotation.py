import collections

from annofabapi.models import TaskPhase, TaskStatus

from annofabcli.annotation_zip.count_annotation import CountAnnotationMain
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

    assert actual["annotation_count"] == 3
    assert actual["annotation_count_by_attribute_value"] == {"dog": {"occluded": {"true": 2}}}
    assert "annotation_count_by_label" not in actual
    assert "annotation_count_by_attribute" not in actual
