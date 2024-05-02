from pathlib import Path

from annofabcli.statistics.list_annotation_duration import ListAnnotationDurationByInputData
from annofabcli.statistics.visualize_annotation_duration import (
    plot_annotation_duration_histogram_by_attribute,
    plot_annotation_duration_histogram_by_label,
)

output_dir = Path("./tests/out/statistics/visualize_annotation_duration")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)


ONE_ANNOTATION = {
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


def test__plot_annotation_duration_histogram_by_label() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(ONE_ANNOTATION)]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label.html",
    )


def test__plot_annotation_duration_histogram_by_attribute() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(ONE_ANNOTATION)]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute.html",
    )
