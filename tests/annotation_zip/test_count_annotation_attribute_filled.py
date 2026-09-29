import collections
import json
from pathlib import Path
from typing import cast

import annofabapi
from annofabapi.pydantic_models.task_phase import TaskPhase
from annofabapi.pydantic_models.task_status import TaskStatus

from annofabcli.annotation_zip.count_annotation_attribute_filled import (
    AnnotationCountByInputData,
    AnnotationCountByTask,
    CountAnnotationAttributeFilledMain,
    ListAnnotationCounterByInputData,
    convert_annotation_count_list_by_input_data_to_by_task,
)
from annofabcli.common.enums import OutputFormat

output_dir = Path("./tests/out/annotation_zip/count_annotation_attribute_filled")
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
            "updated_datetime": "2023-10-01T00:00:00Z",
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

    def test_get_annotation_count__target_labelsを指定した場合は指定ラベルのみ集計する(self):
        annotation = {
            "project_id": "project1",
            "task_id": "task1",
            "task_phase": "acceptance",
            "task_phase_stage": 1,
            "task_status": "complete",
            "input_data_id": "input1",
            "input_data_name": "input1",
            "details": [
                {"label": "bird", "attributes": {"weight": 4}},
                {"label": "climatic", "attributes": {"weather": "sunny"}},
            ],
            "updated_datetime": "2023-10-01T00:00:00Z",
        }

        counter = ListAnnotationCounterByInputData(target_labels=["bird"]).get_annotation_count(annotation)

        assert counter.annotation_attribute_counts == collections.Counter({("bird", "weight", "filled"): 1})

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
            updated_datetime="2023-10-01T00:00:00Z",
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
            updated_datetime="2023-10-01T00:00:00Z",
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


def test_print_annotation_count_タスクのフェーズとステータスで集計する(tmp_path: Path):
    output_file = tmp_path / "summary.json"
    main = CountAnnotationAttributeFilledMain(cast(annofabapi.Resource, None))

    main.print_annotation_count(
        data_dir / "simple-annotations.zip",
        output_file,
        ["task_phase", "task_status"],
        OutputFormat.JSON,
    )

    with output_file.open(encoding="utf-8") as file:
        actual = json.load(file)
    assert len(actual) == 2
    assert [(item["task_phase"], item["task_status"]) for item in actual] == [
        ("acceptance", "not_started"),
        ("acceptance", "complete"),
    ]
    assert [item["task_count"] for item in actual] == [1, 1]
    assert [item["input_data_count"] for item in actual] == [2, 2]
    assert actual[0]["annotation_attribute_counts"]["climatic"]["weather"] == {"filled": 2}
    assert actual[1]["annotation_attribute_counts"]["Cat"]["weight"] == {"filled": 2}
