import collections
from pathlib import Path

from annofabcli.statistics.list_annotation_count import (
    AnnotationSpecs,
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
            "updated_datetime": "2023-10-01T00:00:00Z",
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


class TestAnnotationSpecs:
    """AnnotationSpecsクラスのテスト"""

    def test_get_attribute_name_keys_by_attribute_names(self):
        """get_attribute_name_keys_by_attribute_namesメソッドのテスト"""
        # モックデータを作成
        from unittest.mock import MagicMock

        mock_service = MagicMock()
        # V2形式のアノテーション仕様
        mock_service.api.get_annotation_specs.return_value = (
            {
                "labels": [
                    {
                        "label_id": "label1",
                        "label_name": {"messages": [{"lang": "en-US", "message": "car"}]},
                        "annotation_type": "bounding_box",
                        "additional_data_definitions": ["attr1", "attr2"],
                    },
                    {
                        "label_id": "label2",
                        "label_name": {"messages": [{"lang": "en-US", "message": "bike"}]},
                        "annotation_type": "bounding_box",
                        "additional_data_definitions": ["attr3"],
                    },
                ],
                "additionals": [
                    {
                        "additional_data_definition_id": "attr1",
                        "name": {"messages": [{"lang": "en-US", "message": "color"}]},
                        "type": "text",
                    },
                    {
                        "additional_data_definition_id": "attr2",
                        "name": {"messages": [{"lang": "en-US", "message": "size"}]},
                        "type": "integer",
                    },
                    {
                        "additional_data_definition_id": "attr3",
                        "name": {"messages": [{"lang": "en-US", "message": "color"}]},
                        "type": "text",
                    },
                ],
            },
            None,
        )

        annotation_specs = AnnotationSpecs(mock_service, "project1")

        # "color"という属性名で検索すると、carとbikeの両方が見つかるはず
        result = annotation_specs.get_attribute_name_keys_by_attribute_names(["color"])
        assert len(result) == 2
        assert ("car", "color") in result
        assert ("bike", "color") in result

        # "size"という属性名で検索すると、carのみが見つかるはず
        result = annotation_specs.get_attribute_name_keys_by_attribute_names(["size"])
        assert len(result) == 1
        assert ("car", "size") in result

        # 複数の属性名を指定
        result = annotation_specs.get_attribute_name_keys_by_attribute_names(["color", "size"])
        assert len(result) == 3
        assert ("car", "color") in result
        assert ("bike", "color") in result
        assert ("car", "size") in result

        # 存在しない属性名を指定
        result = annotation_specs.get_attribute_name_keys_by_attribute_names(["nonexistent"])
        assert len(result) == 0
