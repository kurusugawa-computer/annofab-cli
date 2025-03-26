import copy
from pathlib import Path
from typing import Any
from unittest import mock

from annofabapi.models import TaskPhase, TaskStatus

from annofabcli.common.enums import FormatArgument
from annofabcli.task.list_tasks_added_task_history import (
    AddingAdditionalInfoToTask,
    ListTasksAddedTaskHistoryMain,
    TasksAddedTaskHistoryOutput,
    get_completed_datetime,
    get_first_acceptance_completed_datetime,
    get_first_acceptance_reached_datetime,
    get_post_rejection_acceptance_worktime_hour,
    get_post_rejection_annotation_worktime_hour,
    get_post_rejection_inspection_worktime_hour,
    get_task_created_datetime,
    is_acceptance_phase_skipped,
    is_inspection_phase_skipped,
)

task_histories: list[dict[str, Any]] = [
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "555b5ccc-6c80-4c8f-b22f-8c5fd7ef274f",
        "started_datetime": "2025-03-23T16:14:33.796+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "bb0e04bc-4fe8-4eb2-8f5f-556d54b704cb",
        "started_datetime": "2025-03-23T16:14:49.992+09:00",
        "ended_datetime": "2025-03-23T16:14:53.657+09:00",
        "accumulated_labor_time_milliseconds": "PT3.665S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "18edf828-c702-41a7-aa0d-367ce1a0f0e0",
        "started_datetime": "2025-03-23T16:14:53.659+09:00",
        "ended_datetime": "2025-03-23T16:14:53.659+09:00",
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "c15053ed-9813-4a16-a77a-a852daee7782",
        "started_datetime": "2025-03-23T16:14:53.661+09:00",
        "ended_datetime": "2025-03-23T16:14:53.661+09:00",
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "e471f859-7cc9-4828-a6d4-a9b163f5ef67",
        "started_datetime": "2025-03-23T16:15:55.674+09:00",
        "ended_datetime": "2025-03-23T16:16:11.884+09:00",
        "accumulated_labor_time_milliseconds": "PT16.21S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "3345b4a9-610c-47a0-910a-3285ffa96e22",
        "started_datetime": "2025-03-23T16:16:17.631+09:00",
        "ended_datetime": "2025-03-23T16:16:27.045+09:00",
        "accumulated_labor_time_milliseconds": "PT9.414S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "62f6ce58-1684-4b8b-8ea4-c3cd00cf980f",
        "started_datetime": "2025-03-23T16:16:31.062+09:00",
        "ended_datetime": "2025-03-23T16:16:31.062+09:00",
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "d73c5943-949e-4dbd-a01e-a7d8e7f7418d",
        "started_datetime": "2025-03-23T16:16:52.135+09:00",
        "ended_datetime": "2025-03-23T16:16:55.953+09:00",
        "accumulated_labor_time_milliseconds": "PT3.818S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "3bee8257-ca11-4f48-8a9c-6379e2a7a1d6",
        "started_datetime": "2025-03-23T16:16:55.954+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "122c6daa-b834-4c54-ba3f-86fe21b5f936",
        "started_datetime": "2025-03-23T16:17:06.434+09:00",
        "ended_datetime": "2025-03-23T16:17:13.042+09:00",
        "accumulated_labor_time_milliseconds": "PT6.608S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "e88ff387-7b17-430d-acb4-360deb956c2c",
        "started_datetime": "2025-03-23T16:17:13.043+09:00",
        "ended_datetime": None,
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "f084a3a5-1cdb-4839-9317-0e85fbea87ae",
        "started_datetime": "2025-03-23T16:17:17.884+09:00",
        "ended_datetime": "2025-03-23T16:17:17.884+09:00",
        "accumulated_labor_time_milliseconds": "PT0S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": None,
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "382dbb13-f13c-4758-9337-b1335e0d923f",
        "started_datetime": "2025-03-23T16:17:22.852+09:00",
        "ended_datetime": "2025-03-23T16:17:38.245+09:00",
        "accumulated_labor_time_milliseconds": "PT15.393S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "793c4098-26a3-46dd-842c-c94faa6350f0",
        "started_datetime": "2025-03-23T16:18:03.989+09:00",
        "ended_datetime": "2025-03-23T16:18:14.638+09:00",
        "accumulated_labor_time_milliseconds": "PT10.649S",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "514e30a5-9bc5-4d0c-941b-976d4da468dd",
        "started_datetime": "2025-03-23T16:18:19.245+09:00",
        "ended_datetime": "2025-03-23T16:18:36.659+09:00",
        "accumulated_labor_time_milliseconds": "PT17.414S",
        "phase": "inspection",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
    {
        "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
        "task_id": "20250323-1",
        "task_history_id": "064f6af7-834e-4239-85ce-460fa86bc584",
        "started_datetime": "2025-03-23T16:18:39.818+09:00",
        "ended_datetime": "2025-03-23T16:18:47.494+09:00",
        "accumulated_labor_time_milliseconds": "PT7.676S",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
    },
]


def test__get_post_rejection_annotation_worktime_hour():
    assert get_post_rejection_annotation_worktime_hour([]) == 0
    actual_seconds = get_post_rejection_annotation_worktime_hour(task_histories) * 3600
    assert int(actual_seconds) == 23


def test__get_post_rejection_inspection_worktime_hour():
    assert get_post_rejection_inspection_worktime_hour([]) == 0
    actual_seconds = get_post_rejection_inspection_worktime_hour(task_histories) * 3600
    assert int(actual_seconds) == 39


def test__get_post_rejection_acceptance_worktime_hour():
    assert get_post_rejection_acceptance_worktime_hour([]) == 0
    actual_seconds = get_post_rejection_acceptance_worktime_hour(task_histories) * 3600
    assert int(actual_seconds) == 7


def test__get_completed_datetime():
    # 受入完了状態のタスク
    task = {
        "task_id": "20250323-1",
        "phase": TaskPhase.ACCEPTANCE.value,
        "status": TaskStatus.COMPLETE.value,
    }
    # 最後の履歴の終了日時が受入完了日時になる
    assert get_completed_datetime(task, task_histories) == "2025-03-23T16:18:47.494+09:00"

    # 受入完了状態ではないタスク
    task = {
        "task_id": "20250323-1",
        "phase": TaskPhase.ANNOTATION.value,
        "status": TaskStatus.WORKING.value,
    }
    assert get_completed_datetime(task, task_histories) is None


def test__get_task_created_datetime():
    task = {
        "task_id": "20250323-1",
        "operation_updated_datetime": "2025-03-23T16:00:00.000+09:00",
    }
    # 先頭の履歴のstarted_datetimeがタスク作成日時
    assert get_task_created_datetime(task, task_histories) == "2025-03-23T16:14:33.796+09:00"

    # 履歴が空の場合
    assert get_task_created_datetime(task, []) is None


def test__get_first_acceptance_completed_datetime():
    # 初めて受入完了状態になった日時を取得
    # 実際の値を確認
    result = get_first_acceptance_completed_datetime(task_histories)
    assert result == "2025-03-23T16:14:53.661+09:00"

    # 受入完了状態がない場合
    task_histories_without_acceptance = [h for h in task_histories if h["phase"] != "acceptance"]
    assert get_first_acceptance_completed_datetime(task_histories_without_acceptance) is None


def test__get_first_acceptance_reached_datetime():
    # 初めて受入フェーズに到達した日時を取得
    # 受入フェーズの履歴の前の履歴の終了日時
    for i, history in enumerate(task_histories):
        if history["phase"] == "acceptance":
            expected_datetime = task_histories[i - 1]["ended_datetime"]
            break

    assert get_first_acceptance_reached_datetime(task_histories) == expected_datetime

    # 受入フェーズがない場合
    task_histories_without_acceptance = [h for h in task_histories if h["phase"] != "acceptance"]
    assert get_first_acceptance_reached_datetime(task_histories_without_acceptance) is None


def test__is_acceptance_phase_skipped():
    # 現在のタスク履歴では受入フェーズはスキップされていない
    assert is_acceptance_phase_skipped(task_histories) is False

    # スキップされた場合のテスト
    skipped_histories = copy.deepcopy(task_histories)
    # スキップされた履歴を追加
    skipped_histories.append(
        {
            "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
            "task_id": "20250323-1",
            "task_history_id": "skipped-id",
            "started_datetime": "2025-03-23T16:19:00.000+09:00",
            "ended_datetime": "2025-03-23T16:19:00.000+09:00",
            "accumulated_labor_time_milliseconds": "PT0S",
            "phase": "acceptance",
            "phase_stage": 1,
            "account_id": None,
            "sampling": True,  # スキップされた場合はsamplingがTrue
        }
    )
    # モックを使用してスキップされた履歴のインデックスを返す関数をモック
    with mock.patch(
        "annofabcli.task.list_tasks_added_task_history.get_task_history_index_skipped_acceptance", return_value=[len(skipped_histories) - 1]
    ):
        assert is_acceptance_phase_skipped(skipped_histories) is True


def test__is_inspection_phase_skipped():
    # 現在のタスク履歴では検査フェーズはスキップされていない
    assert is_inspection_phase_skipped(task_histories) is False

    # スキップされた場合のテスト
    skipped_histories = copy.deepcopy(task_histories)
    # スキップされた履歴を追加
    skipped_histories.append(
        {
            "project_id": "58a2a621-7d4b-41e7-927b-cdc570c1114a",
            "task_id": "20250323-1",
            "task_history_id": "skipped-id",
            "started_datetime": "2025-03-23T16:19:00.000+09:00",
            "ended_datetime": "2025-03-23T16:19:00.000+09:00",
            "accumulated_labor_time_milliseconds": "PT0S",
            "phase": "inspection",
            "phase_stage": 1,
            "account_id": None,
            "sampling": True,  # スキップされた場合はsamplingがTrue
        }
    )
    # モックを使用してスキップされた履歴のインデックスを返す関数をモック
    with mock.patch(
        "annofabcli.task.list_tasks_added_task_history.get_task_history_index_skipped_inspection", return_value=[len(skipped_histories) - 1]
    ):
        assert is_inspection_phase_skipped(skipped_histories) is True


class TestAddingAdditionalInfoToTask:
    def test_add_additional_info_to_task(self):
        # モックサービスの作成
        service_mock = mock.MagicMock()
        project_id = "58a2a621-7d4b-41e7-927b-cdc570c1114a"

        # AddingAdditionalInfoToTaskのインスタンス作成
        obj = AddingAdditionalInfoToTask(service_mock, project_id)

        # visualizeのadd_properties_to_taskをモック
        obj.visualize.add_properties_to_task = mock.MagicMock()

        # テスト対象の関数を実行
        task = {"task_id": "20250323-1"}
        obj.add_additional_info_to_task(task)

        # visualizeのadd_properties_to_taskが呼ばれたことを確認
        obj.visualize.add_properties_to_task.assert_called_once_with(task)

    def test_add_task_history_additional_info_to_task(self):
        # モックサービスの作成
        service_mock = mock.MagicMock()
        project_id = "58a2a621-7d4b-41e7-927b-cdc570c1114a"

        # AddingAdditionalInfoToTaskのインスタンス作成
        obj = AddingAdditionalInfoToTask(service_mock, project_id)

        # _add_task_history_info_by_phaseをモック
        obj._add_task_history_info_by_phase = mock.MagicMock()

        # テスト対象の関数を実行
        task = {
            "task_id": "20250323-1",
            "phase": TaskPhase.ACCEPTANCE.value,
            "status": TaskStatus.COMPLETE.value,
        }
        obj.add_task_history_additional_info_to_task(task, task_histories)

        # _add_task_history_info_by_phaseが各フェーズで呼ばれたことを確認
        assert obj._add_task_history_info_by_phase.call_count == 3
        obj._add_task_history_info_by_phase.assert_any_call(task, task_histories, phase=TaskPhase.ANNOTATION)
        obj._add_task_history_info_by_phase.assert_any_call(task, task_histories, phase=TaskPhase.INSPECTION)
        obj._add_task_history_info_by_phase.assert_any_call(task, task_histories, phase=TaskPhase.ACCEPTANCE)


class TestListTasksAddedTaskHistoryMain:
    def test_main(self):
        # モックサービスの作成
        service_mock = mock.MagicMock()
        project_id = "58a2a621-7d4b-41e7-927b-cdc570c1114a"

        # ListTasksMainのモック
        with mock.patch("annofabcli.task.list_tasks_added_task_history.ListTasksMain") as mock_list_tasks:
            # get_task_listの戻り値を設定
            mock_list_tasks.return_value.get_task_list.return_value = [{"task_id": "20250323-1"}]

            # AddingAdditionalInfoToTaskのモック
            with mock.patch("annofabcli.task.list_tasks_added_task_history.AddingAdditionalInfoToTask") as mock_adding:
                # ListTasksAddedTaskHistoryMainのインスタンス作成
                main_obj = ListTasksAddedTaskHistoryMain(service_mock, project_id)

                # APIのget_task_historiesの戻り値を設定
                service_mock.api.get_task_histories.return_value = (task_histories, {})

                # テスト対象の関数を実行
                result = main_obj.main(task_query=None, task_id_list=None)

                # 結果の確認
                assert len(result) == 1
                assert result[0]["task_id"] == "20250323-1"

                # 各メソッドが呼ばれたことを確認
                mock_list_tasks.assert_called_once_with(service_mock, project_id)
                mock_list_tasks.return_value.get_task_list.assert_called_once_with(project_id, task_id_list=None, task_query=None)
                mock_adding.assert_called_once_with(service_mock, project_id=project_id)
                mock_adding.return_value.add_additional_info_to_task.assert_called_once()
                mock_adding.return_value.add_task_history_additional_info_to_task.assert_called_once()
                service_mock.api.get_task_histories.assert_called_once_with(project_id, "20250323-1")


class TestTasksAddedTaskHistoryOutput:
    def test_output_csv(self):
        # テスト用のタスクリスト - 必要なすべてのカラムを含める
        task_list: list[dict[str, Any]] = [
            {
                "task_id": "20250323-1",
                "phase": "annotation",
                "phase_stage": 1,
                "status": "working",
                "created_datetime": "2025-03-23T16:14:33.796+09:00",
                "started_datetime": "2025-03-23T16:14:49.992+09:00",
                "updated_datetime": "2025-03-23T16:18:47.494+09:00",
                "operation_updated_datetime": "2025-03-23T16:18:47.494+09:00",
                "account_id": "00589ed0-dd63-40db-abb2-dfe5e13c8299",
                "user_id": "user1",
                "username": "ユーザー1",
                "input_data_count": 1,
                "metadata": {},
                "sampling": False,
                "worktime_hour": 1.0,
                "annotation_worktime_hour": 0.5,
                "inspection_worktime_hour": 0.3,
                "acceptance_worktime_hour": 0.2,
                "number_of_rejections_by_inspection": 0,
                "number_of_rejections_by_acceptance": 0,
                "first_acceptance_reached_datetime": "2025-03-23T16:14:53.659+09:00",
                "first_acceptance_completed_datetime": "2025-03-23T16:14:53.661+09:00",
                "completed_datetime": None,
                "inspection_is_skipped": False,
                "acceptance_is_skipped": False,
                "first_annotation_user_id": "user1",
                "first_annotation_username": "ユーザー1",
                "first_annotation_started_datetime": "2025-03-23T16:14:49.992+09:00",
                "first_annotation_worktime_hour": 0.5,
                "first_inspection_user_id": "user2",
                "first_inspection_username": "ユーザー2",
                "first_inspection_started_datetime": "2025-03-23T16:17:06.434+09:00",
                "first_inspection_worktime_hour": 0.3,
                "first_acceptance_user_id": "user3",
                "first_acceptance_username": "ユーザー3",
                "first_acceptance_started_datetime": "2025-03-23T16:15:55.674+09:00",
                "first_acceptance_worktime_hour": 0.2,
                "post_rejection_annotation_worktime_hour": 0.0,
                "post_rejection_inspection_worktime_hour": 0.0,
                "post_rejection_acceptance_worktime_hour": 0.0,
            }
        ]

        # TasksAddedTaskHistoryOutputのインスタンス作成
        output_obj = TasksAddedTaskHistoryOutput(task_list)

        # _get_output_target_columnsをモック
        with (
            mock.patch.object(TasksAddedTaskHistoryOutput, "_get_output_target_columns", return_value=["task_id", "phase"]),
            mock.patch("annofabcli.task.list_tasks_added_task_history.print_csv") as mock_print_csv,
        ):
            # テスト対象の関数を実行
            output_path = Path("output.csv")
            output_obj.output(output_path, output_format=FormatArgument.CSV)

            # print_csvが呼ばれたことを確認
            mock_print_csv.assert_called_once()

    def test_output_json(self):
        # テスト用のタスクリスト
        task_list = [{"task_id": "20250323-1", "phase": "annotation"}]

        # TasksAddedTaskHistoryOutputのインスタンス作成
        output_obj = TasksAddedTaskHistoryOutput(task_list)

        # print_jsonをモック
        with mock.patch("annofabcli.task.list_tasks_added_task_history.print_json") as mock_print_json:
            # テスト対象の関数を実行（JSON形式）
            output_path = Path("output.json")
            output_obj.output(output_path, output_format=FormatArgument.JSON)

            # print_jsonが呼ばれたことを確認
            mock_print_json.assert_called_once_with(task_list, is_pretty=False, output=output_path)

            # モックをリセット
            mock_print_json.reset_mock()

            # テスト対象の関数を実行（PRETTY_JSON形式）
            output_obj.output(output_path, output_format=FormatArgument.PRETTY_JSON)

            # print_jsonが呼ばれたことを確認
            mock_print_json.assert_called_once_with(task_list, is_pretty=True, output=output_path)

    def test_output_empty(self):
        # 空のタスクリスト
        task_list: list[dict[str, Any]] = []

        # TasksAddedTaskHistoryOutputのインスタンス作成
        output_obj = TasksAddedTaskHistoryOutput(task_list)

        # print_csvとprint_jsonをモック
        with (
            mock.patch("annofabcli.task.list_tasks_added_task_history.print_csv") as mock_print_csv,
            mock.patch("annofabcli.task.list_tasks_added_task_history.print_json") as mock_print_json,
        ):
            # テスト対象の関数を実行
            output_path = Path("output.csv")
            output_obj.output(output_path, output_format=FormatArgument.CSV)

            # タスクリストが空の場合は出力関数が呼ばれないことを確認
            mock_print_csv.assert_not_called()
            mock_print_json.assert_not_called()
