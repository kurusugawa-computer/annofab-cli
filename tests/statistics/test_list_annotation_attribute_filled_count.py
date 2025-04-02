from pathlib import Path

from annofabcli.statistics.list_annotation_attribute_filled_count import (
    ListAnnotationAttributeFilledCountMain,
    ListAnnotationCounterByInputData,
)

output_dir = Path("./tests/out/statistics/list_annotation_attribute_filled_count")
data_dir = Path("./tests/data/statistics/")
output_dir.mkdir(exist_ok=True, parents=True)


class TestListAnnotationCounterByInputData:
    def test_get_annotation_count(self):
        annotation = {
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
                        "notes": "foo",
                        "occluded": True,
                    },
                },
                {
                    "label": "bird",
                    "attributes": {
                        "notes": "",
                        "occluded": True,
                    },
                },
                {"label": "climatic", "attributes": {"weather": None}},
            ],
        }

        counter = ListAnnotationCounterByInputData().get_annotation_count(annotation)
        assert counter.input_data_id == "input1"
        assert counter.task_id == "task1"
        assert counter.annotation_attribute_counts == {
            ("bird", "notes", "filled"): 1,
            ("bird", "notes", "empty"): 1,
            ("bird", "occluded", "filled"): 2,
            ("climatic", "weather", "empty"): 1,
        }

    def test_get_annotation_count_list(self):
        counter_list = ListAnnotationCounterByInputData().get_annotation_count_list(data_dir / "simple-annotations.zip")
        print(counter_list)


class TestListAnnotationAttributeFilledCountMain:
    def test_print_annotation_count_csv_by_input_data(self):
        counter_list = ListAnnotationCounterByInputData().get_annotation_count_list(data_dir / "simple-annotations.zip")
        ListAnnotationAttributeFilledCountMain(None).print_annotation_count_csv_by_input_data(
            counter_list,
            output_file=output_dir / "attributes_filled_count_by_input_data.csv",
            attribute_names=None,
        )

    def test_print_annotation_count_csv_by_task(self):
        counter_list = ListAnnotationCounterByInputData().get_annotation_count_list(data_dir / "simple-annotations.zip")
        ListAnnotationAttributeFilledCountMain(None).print_annotation_count_csv_by_task(
            counter_list,
            output_file=output_dir / "attributes_filled_count_by_task.csv",
            attribute_names=None,
        )
