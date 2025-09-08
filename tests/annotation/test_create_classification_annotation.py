from unittest.mock import MagicMock

from annofabapi.models import DefaultAnnotationType

from annofabcli.annotation.create_classification_annotation import (
    CreateClassificationAnnotationMain,
)

# テスト用のモックデータ
annotation_specs = {
    "labels": [
        {
            "label_id": "label1",
            "label_name": {"ja": "ラベル1", "en": "label1"},
            "annotation_type": DefaultAnnotationType.CLASSIFICATION.value,
        },
        {
            "label_id": "label2",
            "label_name": {"ja": "ラベル2", "en": "label2"},
            "annotation_type": DefaultAnnotationType.CLASSIFICATION.value,
        },
        {
            "label_id": "label3",
            "label_name": {"ja": "ラベル3", "en": "label3"},
            "annotation_type": DefaultAnnotationType.BOUNDING_BOX.value,  # Classification以外
        },
    ],
    "attributes": [],
}

project = {
    "project_id": "test_project_id",
    "input_data_type": "image",
    "configuration": {
        "plugin_id": None,
    },
}

task = {
    "task_id": "test_task_id",
    "status": "not_started",
    "account_id": None,
    "updated_datetime": "2023-01-01T00:00:00.000Z",
}

input_data_list = [
    {
        "input_data_id": "input1",
    },
    {
        "input_data_id": "input2",
    },
]

existing_annotation = {
    "details": [],
    "updated_datetime": "2023-01-01T00:00:00.000Z",
}


class TestCreateClassificationAnnotationMain:
    def setup_method(self):
        """各テストメソッドの前に実行される"""
        # モックサービスの作成
        self.mock_service = MagicMock()
        self.mock_service.api.account_id = "test_account_id"
        self.mock_service.wrapper.get_task_or_none.return_value = task
        self.mock_service.wrapper.get_input_data_list.return_value = input_data_list
        self.mock_service.api.get_annotation_specs.return_value = (annotation_specs, None)
        self.mock_service.api.get_editor_annotation.return_value = (existing_annotation, None)
        self.mock_service.api.put_annotation.return_value = None

        self.main_obj = CreateClassificationAnnotationMain(
            service=self.mock_service,
            project_id="test_project_id",
            all_yes=True,  # 確認をスキップ
            is_force=False,
        )

    def test_create_classification_annotation_for_task_success(self):
        """正常なケース：全体アノテーションが正しく作成される"""
        labels = ["label1", "label2"]

        result = self.main_obj.create_classification_annotation_for_task("test_task_id", labels)

        # 2つのラベル × 2つの入力データ = 4つのアノテーションが作成されることを確認
        assert result == 4

        # put_annotationが入力データの数だけ呼ばれることを確認
        assert self.mock_service.api.put_annotation.call_count == 2

    def test_create_classification_annotation_for_task_nonexistent_label(self):
        """存在しないラベル名を指定した場合"""
        labels = ["nonexistent_label"]

        result = self.main_obj.create_classification_annotation_for_task("test_task_id", labels)

        # アノテーションが作成されないことを確認
        assert result == 0
        assert self.mock_service.api.put_annotation.call_count == 0

    def test_create_classification_annotation_for_task_non_classification_label(self):
        """Classification以外のラベルを指定した場合"""
        labels = ["label3"]  # BOUNDING_BOXのラベル

        result = self.main_obj.create_classification_annotation_for_task("test_task_id", labels)

        # アノテーションが作成されないことを確認
        assert result == 0
        assert self.mock_service.api.put_annotation.call_count == 0

    def test_create_classification_annotation_for_task_already_exists(self):
        """既に全体アノテーションが存在する場合"""
        # 既存のアノテーションを設定
        existing_annotation_with_data = {
            "details": [
                {
                    "annotation_id": "label1",  # label1のアノテーションが既に存在
                    "label_id": "label1",
                }
            ],
            "updated_datetime": "2023-01-01T00:00:00.000Z",
        }
        self.mock_service.api.get_editor_annotation.return_value = (existing_annotation_with_data, None)

        labels = ["label1", "label2"]

        result = self.main_obj.create_classification_annotation_for_task("test_task_id", labels)

        # label2のみが作成される（2つの入力データ）
        assert result == 2

    def test_create_classification_annotation_for_task_nonexistent_task(self):
        """存在しないタスクを指定した場合"""
        self.mock_service.wrapper.get_task_or_none.return_value = None

        result = self.main_obj.create_classification_annotation_for_task("nonexistent_task", ["label1"])

        assert result == 0

    def test_create_classification_annotation_for_task_working_task(self):
        """作業中のタスクを指定した場合"""
        working_task = task.copy()
        working_task["status"] = "working"
        self.mock_service.wrapper.get_task_or_none.return_value = working_task

        result = self.main_obj.create_classification_annotation_for_task("test_task_id", ["label1"])

        assert result == 0

    def test_create_classification_annotation_for_task_complete_task(self):
        """受入完了のタスクを指定した場合"""
        complete_task = task.copy()
        complete_task["status"] = "complete"
        self.mock_service.wrapper.get_task_or_none.return_value = complete_task

        result = self.main_obj.create_classification_annotation_for_task("test_task_id", ["label1"])

        assert result == 0

    def test_create_classification_annotation_for_task_with_force(self):
        """--forceオプションで担当者を変更する場合"""
        # 他人が担当中のタスク
        assigned_task = task.copy()
        assigned_task["account_id"] = "other_account_id"
        assigned_task["phase"] = "annotation"
        self.mock_service.wrapper.get_task_or_none.return_value = assigned_task
        self.mock_service.wrapper.change_task_operator.return_value = assigned_task

        main_obj_with_force = CreateClassificationAnnotationMain(
            service=self.mock_service,
            project_id="test_project_id",
            all_yes=True,
            is_force=True,
        )

        labels = ["label1"]

        result = main_obj_with_force.create_classification_annotation_for_task("test_task_id", labels)

        # 担当者変更が2回呼ばれる（変更と復元）
        assert self.mock_service.wrapper.change_task_operator.call_count == 2
        # アノテーションが作成される
        assert result == 2

    def test_main_with_parallelism(self):
        """並列処理のテスト"""
        # このテストは実際のmultiprocessingを避けてモックで簡単にテスト
        task_ids = ["task1", "task2"]
        labels = ["label1"]

        # 並列処理なし
        self.main_obj.main(task_ids, labels, parallelism=None)

        # execute_taskが呼ばれた回数を確認
        # 実際の実装では、各タスクに対してcreate_classification_annotation_for_taskが呼ばれる
