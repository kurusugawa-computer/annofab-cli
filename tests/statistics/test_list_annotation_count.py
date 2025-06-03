import collections
from pathlib import Path

from annofabcli.statistics.list_annotation_count import (
    AttributeCountCsv,
    LabelCountCsv,
    ListAnnotationCounterByInputData,
    ListAnnotationCounterByTask,
)

output_dir = Path("./tests/out/statistics/list_annotation_count")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)


class TestListAnnotationCounterByInputData:
    def test_get_annotation_counter(self):
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

        counter = ListAnnotationCounterByInputData().get_annotation_counter(annotation)
        assert counter.input_data_id == "input1"
        assert counter.task_id == "task1"
        assert counter.annotation_count_by_label == collections.Counter({"bird": 2, "climatic": 1})
        assert counter.annotation_count_by_attribute == collections.Counter(
            {
                ("bird", "weight", "4"): 1,
                ("bird", "weight", "3"): 1,
                ("bird", "occluded", "true"): 2,
                ("climatic", "weather", "sunny"): 1,
            }
        )

        counter2 = ListAnnotationCounterByInputData(target_labels=["climatic"], target_attribute_names=[("bird", "occluded")]).get_annotation_counter(annotation)
        assert counter2.annotation_count_by_label == collections.Counter({"climatic": 1})
        assert counter2.annotation_count_by_attribute == collections.Counter(
            {
                ("bird", "occluded", "true"): 2,
            }
        )

    def test_get_annotation_counter_list(self):
        counter_list = ListAnnotationCounterByInputData().get_annotation_counter_list(data_dir / "simple-annotations.zip")
        assert len(counter_list) == 4


class TestListAnnotationCounterByTask:
    def test_get_annotation_counter_list(self):
        counter_list = ListAnnotationCounterByTask().get_annotation_counter_list(data_dir / "simple-annotations.zip")
        assert len(counter_list) == 2


class TestLabelCountCsv:
    def test_print_csv_by_input_data(self):
        counter_list = ListAnnotationCounterByInputData().get_annotation_counter_list(data_dir / "simple-annotations.zip")
        LabelCountCsv().print_csv_by_input_data(
            counter_list,
            output_file=output_dir / "labels_count_by_input_data.csv",
            prior_label_columns=["dog", "human"],
        )

    def test_print_labels_count_csv(self):
        counter_list = ListAnnotationCounterByTask().get_annotation_counter_list(data_dir / "simple-annotations.zip")

        LabelCountCsv().print_csv_by_task(
            counter_list,
            output_file=output_dir / "labels_count_by_input_data.csv",
            prior_label_columns=["dog", "human"],
        )


class TestAttributeCountCsv:
    def test_print_csv_by_input_data(self):
        counter_list = ListAnnotationCounterByInputData().get_annotation_counter_list(data_dir / "simple-annotations.zip")
        AttributeCountCsv().print_csv_by_input_data(
            counter_list,
            output_file=output_dir / "list_annotation_count/attributes_count_by_input_data.csv",
            prior_attribute_columns=[("Cat", "occluded", "True"), ("climatic", "temparature", "20")],
        )

    def test_print_csv_by_task(self):
        counter_list = ListAnnotationCounterByTask().get_annotation_counter_list(data_dir / "simple-annotations.zip")
        AttributeCountCsv().print_csv_by_task(
            counter_list,
            output_file=output_dir / "attributes_count_by_task.csv",
            prior_attribute_columns=[("Cat", "occluded", "true"), ("climatic", "temparature", "20")],
        )
