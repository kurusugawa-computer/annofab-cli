from pathlib import Path

from annofabcli.statistics.list_annotation_count import ListAnnotationCounterByInputData, ListAnnotationCounterByTask
from annofabcli.statistics.visualize_annotation_count import GroupBy, plot_attribute_histogram, plot_label_histogram

output_dir = Path("./tests/out/statistics/visualize_annotation_count")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)


def test_plot_label_histogram() -> None:
    counter_list = ListAnnotationCounterByInputData().get_annotation_counter_list(data_dir / "simple-annotations.zip")

    plot_label_histogram(
        counter_list,
        group_by=GroupBy.INPUT_DATA_ID,
        output_file=output_dir / "labels_count_by_input_data.html",
    )


def test_plot_label_histogram__arrange_bin_edgeにTrueを指定() -> None:
    counter_list = ListAnnotationCounterByInputData().get_annotation_counter_list(data_dir / "simple-annotations.zip")

    plot_label_histogram(
        counter_list,
        group_by=GroupBy.INPUT_DATA_ID,
        output_file=output_dir / "test_plot_label_histogram__arrange_bin_edgeにTrueを指定.html",
        arrange_bin_edge=True,
    )


def test_plot_label_histogram__bin_widthを指定() -> None:
    counter_list = ListAnnotationCounterByInputData().get_annotation_counter_list(data_dir / "simple-annotations.zip")

    plot_label_histogram(counter_list, group_by=GroupBy.INPUT_DATA_ID, output_file=output_dir / "test_plot_label_histogram__bin_widthを指定.html", bin_width=10)


def test_plot_label_histogram__metadataを指定() -> None:
    counter_list = ListAnnotationCounterByInputData().get_annotation_counter_list(data_dir / "simple-annotations.zip")

    plot_label_histogram(
        counter_list,
        group_by=GroupBy.INPUT_DATA_ID,
        output_file=output_dir / "test_plot_label_histogram__metadataを指定.html",
        metadata={"project_id": "id", "project_title": "title1"},
    )


def test_plot_attribute_histogram() -> None:
    counter_list = ListAnnotationCounterByTask().get_annotation_counter_list(data_dir / "simple-annotations.zip")

    plot_attribute_histogram(
        counter_list,
        group_by=GroupBy.TASK_ID,
        output_file=output_dir / "attributes_count_by_task.html",
    )


def test__plot_attribute_histogram__arrange_bin_edgeにTrueを指定() -> None:
    counter_list = ListAnnotationCounterByTask().get_annotation_counter_list(data_dir / "simple-annotations.zip")

    plot_attribute_histogram(
        counter_list,
        group_by=GroupBy.TASK_ID,
        output_file=output_dir / "test__plot_attribute_histogram__arrange_bin_edgeにTrueを指定.html",
        arrange_bin_edge=True,
    )


def test__plot_annotation_duration_histogram_by_attribute__bin_widthを指定() -> None:
    counter_list = ListAnnotationCounterByTask().get_annotation_counter_list(data_dir / "simple-annotations.zip")

    plot_attribute_histogram(
        counter_list,
        group_by=GroupBy.TASK_ID,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute__bin_widthを指定.html",
        bin_width=10,
    )


def test__plot_annotation_duration_histogram_by_attribute__metadataを指定() -> None:
    counter_list = ListAnnotationCounterByTask().get_annotation_counter_list(data_dir / "simple-annotations.zip")

    plot_attribute_histogram(
        counter_list,
        group_by=GroupBy.TASK_ID,
        output_file=output_dir / "test__plot_annotation_duration_histogram_by_attribute__metadataを指定.html",
        metadata={"project_id": "id", "project_title": "title1"},
    )
