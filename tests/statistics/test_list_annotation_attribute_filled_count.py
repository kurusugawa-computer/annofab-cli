import collections
from pathlib import Path

from annofabapi.pydantic_models.task_phase import TaskPhase
from annofabapi.pydantic_models.task_status import TaskStatus

from annofabcli.statistics.list_annotation_attribute_filled_count import (
    AnnotationCountByInputData,
    AnnotationCountByTask,
    ListAnnotationCounterByInputData,
    convert_annotation_count_list_by_input_data_to_by_task,
)

output_dir = Path("./tests/out/statistics/list_annotation_attribute_filled_count")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)


class TestListAnnotationCounterByInputData:
    def test_get_annotation_count(self):
        annotation = {
            "project_id": "project1",
            "task_id": "task1",
            "task_phase": "acceptance",
            "task_phase_stage": 1,
            "task_status": "complete",
            "input_data_id": "input1",
            "input_data_name": "input1",
            "details": [
                {
                    "label": "bird",
                    "attributes": {
                        "weight": 4,
                        "occluded": True,
                    },
                },
                {
                    "label": "bird",
                    "attributes": {
                        "weight": 3,
                        "occluded": True,
                    },
                },
                {"label": "climatic", "attributes": {"weather": "sunny"}},
            ],
        }

        counter = ListAnnotationCounterByInputData().get_annotation_count(annotation)
        assert counter.input_data_id == "input1"
        assert counter.task_id == "task1"
        assert counter.annotation_attribute_counts == collections.Counter(
            {
                ("bird", "weight", "filled"): 2,
                ("bird", "occluded", "filled"): 2,
                ("climatic", "weather", "filled"): 1,
            }
        )

    def test_get_annotation_count_list(self):
        counter_list = ListAnnotationCounterByInputData().get_annotation_count_list(data_dir / "simple-annotations.zip")
        assert len(counter_list) == 4


def test_convert_annotation_count_list_by_input_data_to_by_task():
    input_data_list = [
        AnnotationCountByInputData(
            project_id="project1",
            task_id="task1",
            task_status=TaskStatus.COMPLETE,
            task_phase=TaskPhase.ACCEPTANCE,
            task_phase_stage=1,
            input_data_id="input1",
            input_data_name="input1",
            annotation_attribute_counts={
                ("bird", "notes", "filled"): 1,
                ("bird", "notes", "empty"): 1,
            },
        ),
        AnnotationCountByInputData(
            project_id="project1",
            task_id="task1",
            task_status=TaskStatus.COMPLETE,
            task_phase=TaskPhase.ACCEPTANCE,
            task_phase_stage=1,
            input_data_id="input2",
            input_data_name="input2",
            annotation_attribute_counts={
                ("bird", "notes", "filled"): 1,
            },
        ),
    ]

    task_list = convert_annotation_count_list_by_input_data_to_by_task(input_data_list)
    assert len(task_list) == 1
    task = task_list[0]

    assert task == AnnotationCountByTask(
        project_id="project1",
        task_id="task1",
        task_status=TaskStatus.COMPLETE,
        task_phase=TaskPhase.ACCEPTANCE,
        task_phase_stage=1,
        input_data_count=2,
        annotation_attribute_counts={
            ("bird", "notes", "filled"): 2,
            ("bird", "notes", "empty"): 1,
        },
    )
