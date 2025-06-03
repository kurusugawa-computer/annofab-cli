from pathlib import Path

from annofabcli.statistics.list_annotation_duration import ListAnnotationDurationByInputData
from annofabcli.statistics.visualize_annotation_duration import (
    TimeUnit,
    plot_annotation_duration_histogram_by_attribute,
    plot_annotation_duration_histogram_by_label,
)

output_dir = Path("./tests/out/statistics/visualize_annotation_duration")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)


ANNOTATIONS = [
    {
        "project_id": "project1",
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
    },
    {
        "project_id": "project1",
        "task_id": "task2",
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
                "data": {"begin": 3000, "end": 160000, "_type": "Range"},
                "attributes": {"color": "red"},
            },
            {
                "label": "traffic_light",
                "data": {"begin": 16000, "end": 240000, "_type": "Range"},
                "attributes": {"color": "green"},
            },
            {
                "label": "traffic_light_for_pedestrian",
                "data": {"begin": 4000, "end": 90000, "_type": "Range"},
                "attributes": {"color": "green"},
            },
        ],
    },
]


def test__plot_annotation_duration_histogram_by_label__time_unitに秒を指定する() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__time_unitに秒を指定する.html",
        time_unit=TimeUnit.SECOND,
    )


def test__plot_annotation_duration_histogram_by_label__time_unitに分を指定する() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__time_unitに分を指定する.html",
        time_unit=TimeUnit.MINUTE,
    )


def test__plot_annotation_duration_histogram_by_label__bin_widthを指定する() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__bin_widthを指定する.html",
        time_unit=TimeUnit.MINUTE,
        bin_width=60,
    )


def test__plot_annotation_duration_histogram_by_label__arrange_bin_edgeを指定する() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__arrange_bin_edgeを指定する.html",
        time_unit=TimeUnit.SECOND,
        arrange_bin_edge=True,
    )


def test__plot_annotation_duration_histogram_by_label__bin_widthとarrange_bin_edgeを指定する() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__bin_widthとarrange_bin_edgeを指定する.html",
        time_unit=TimeUnit.MINUTE,
        bin_width=60,
        arrange_bin_edge=True,
    )


def test__plot_annotation_duration_histogram_by_label__metadataを指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_label(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_label__metadataを指定.html",
        time_unit=TimeUnit.SECOND,
        metadata={"project_id": "id", "project_title": "title1"},
    )


def test__plot_annotation_duration_histogram_by_attribute() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute.html",
        time_unit=TimeUnit.SECOND,
    )


def test__plot_annotation_duration_histogram_by_attribute__time_unitに分を指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "plot_annotation_duration_histogram_by_attribute__time_unitに分を指定.html",
        time_unit=TimeUnit.MINUTE,
    )


def test__plot_annotation_duration_histogram_by_attribute__arrange_bin_edgeを指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute__arrange_bin_edgeを指定.html",
        time_unit=TimeUnit.MINUTE,
        arrange_bin_edge=True,
    )


def test__plot_annotation_duration_histogram_by_attribute__bin_widthを指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute__bin_widthを指定.html",
        time_unit=TimeUnit.MINUTE,
        bin_width=60,
    )


def test__plot_annotation_duration_histogram_by_attribute__bin_widthとarrange_bin_edgeを指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute__bin_widthとarrange_bin_edgeを指定.html",
        time_unit=TimeUnit.MINUTE,
        bin_width=60,
        arrange_bin_edge=True,
    )


def test__plot_annotation_duration_histogram_by_attribute__metadataを指定() -> None:
    annotation_duration_list = [ListAnnotationDurationByInputData().get_annotation_duration(e) for e in ANNOTATIONS]

    plot_annotation_duration_histogram_by_attribute(
        annotation_duration_list,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute__metadataを指定.html",
        time_unit=TimeUnit.SECOND,
        metadata={"project_id": "id", "project_title": "title1"},
    )
