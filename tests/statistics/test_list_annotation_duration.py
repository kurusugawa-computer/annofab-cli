import collections
from pathlib import Path

from annofabcli.statistics.list_annotation_duration import (
    ListAnnotationDurationByInputData,
)

output_dir = Path("./tests/out/statistics/list_annotation_duration")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)

ANNOTATION = {
    "task_id": "task1",
    "task_phase": "acceptance",
    "task_phase_stage": 1,
    "task_status": "complete",
    "input_data_id": "input1",
    "input_data_name": "input1",
    "details": [
        {
            "label": "entire_video",
            "data": {"_type": "Classification"},
            "attributes": {"weather": "fine"},
        },
        {
            "label": "traffic_light",
            "data": {"begin": 3000, "end": 16000, "_type": "Range"},
            "attributes": {"color": "red"},
        },
        {
            "label": "traffic_light",
            "data": {"begin": 16000, "end": 24000, "_type": "Range"},
            "attributes": {"color": "green"},
        },
        {
            "label": "traffic_light_for_pedestrian",
            "data": {"begin": 4000, "end": 9000, "_type": "Range"},
            "attributes": {"color": "green"},
        },
    ],
}


class TestListAnnotationDurationByInputData:
    def test_get_annotation_duration(self) -> None:

        annotation_duration = ListAnnotationDurationByInputData().get_annotation_duration(ANNOTATION)
        assert annotation_duration.input_data_id == "input1"
        assert annotation_duration.task_id == "task1"
        assert annotation_duration.annotation_duration_second == 26.0
        assert annotation_duration.annotation_duration_second_by_label == {
            "traffic_light": 21.0,
            "traffic_light_for_pedestrian": 5.0,
        }
        assert annotation_duration.annotation_duration_second_by_attribute == collections.Counter(
            {
                ("traffic_light", "color", "green"): 8.0,
                ("traffic_light", "color", "red"): 13.0,
                ("traffic_light_for_pedestrian", "color", "green"): 5.0,
            }
        )

    def test_get_annotation_duration__target_labels引数を指定する(self) -> None:
        annotation_duration = ListAnnotationDurationByInputData(target_labels=["traffic_light"]).get_annotation_counter(
            ANNOTATION
        )
        assert annotation_duration.annotation_duration_second == 26.0
        assert annotation_duration.annotation_duration_second_by_label == {
            "traffic_light": 21.0,
            "traffic_light_for_pedestrian": 5.0,
        }
        assert annotation_duration.annotation_duration_second_by_attribute == collections.Counter(
            {
                ("traffic_light", "color", "green"): 8.0,
                ("traffic_light", "color", "red"): 13.0,
                ("traffic_light_for_pedestrian", "color", "green"): 5.0,
            }
        )

    # def test_get_annotation_counter_list(self):
    #     counter_list = ListAnnotationCounterByInputData().get_annotation_counter_list(data_dir / "simple-annotations.zip")
    #     assert len(counter_list) == 4
