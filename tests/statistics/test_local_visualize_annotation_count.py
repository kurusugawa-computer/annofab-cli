import collections
from pathlib import Path

from annofabcli.statistics.list_annotation_count import (
    AttributeCountCsv,
    LabelCountCsv,
    ListAnnotationCounterByInputData,
    ListAnnotationCounterByTask,
)
from annofabcli.statistics.visualize_annotation_count import plot_attribute_histogram, plot_label_histogram, GroupBy


output_dir = Path("./tests/out/statistics/visualize_annotation_count")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)


def test_plot_label_histogram():
    counter_list = ListAnnotationCounterByInputData().get_annotation_counter_list(
        data_dir / "simple-annotations.zip"
    )

    plot_label_histogram(
        counter_list,
        group_by=GroupBy.INPUT_DATA_ID,
        output_file=output_dir / "labels_count_by_input_data.html",
    )

def test_plot_attribute_histogram():
    counter_list = ListAnnotationCounterByTask().get_annotation_counter_list(data_dir / "simple-annotations.zip")

    plot_attribute_histogram(
        counter_list,
        group_by=GroupBy.TASK_ID,
        output_file=output_dir / "attributes_count_by_task.html",
    )

