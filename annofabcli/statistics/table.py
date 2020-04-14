# pylint: disable=too-many-lines
import copy
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

import dateutil
import more_itertools
import numpy
import pandas as pd
from annofabapi.dataclass.annotation import SimpleAnnotationDetail
from annofabapi.dataclass.statistics import (
    ProjectAccountStatistics,
    ProjectAccountStatisticsHistory,
    WorktimeStatistics,
    WorktimeStatisticsItem,
)
from annofabapi.models import InputDataId, Inspection, InspectionStatus, Task, TaskHistory, TaskPhase, TaskStatus
from annofabapi.utils import (
    get_number_of_rejections,
    get_task_history_index_skipped_acceptance,
    get_task_history_index_skipped_inspection,
)
from more_itertools import first_true

import annofabcli
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import datetime_to_date, isoduration_to_hour
from annofabcli.statistics.database import AnnotationDict, Database

logger = logging.getLogger(__name__)


class AggregationBy(Enum):
    BY_INPUTS = "by_inputs"
    BY_TASKS = "by_tasks"


class AccountStatisticsValue(Enum):
    TASKS_COMPLETED = "tasks_completed"
    TASKS_REJECTED = "tasks_rejected"
    WORKTIME = "worktime"


class Table:
    """
    Databaseから取得した情報を元にPandas DataFrameを生成するクラス
    チェックポイントファイルがあること前提

    Attributes:
        label_dict: label_idとその名前の辞書
        inspection_phrases_dict: 定型指摘IDとそのコメント
        project_members_dict: account_idとプロジェクトメンバ情報

    """

    #############################################
    # Private
    #############################################

    _task_id_list: Optional[List[str]] = None
    _task_list: Optional[List[Task]] = None
    _inspections_dict: Optional[Dict[str, Dict[InputDataId, List[Inspection]]]] = None
    _annotations_dict: Optional[Dict[str, Dict[InputDataId, Dict[str, Any]]]] = None
    _worktime_statistics: Optional[List[WorktimeStatistics]] = None
    _account_statistics: Optional[List[ProjectAccountStatistics]] = None
    _labor_list: Optional[List[Dict[str, Any]]] = None

    def __init__(
        self, database: Database, task_query_param: Dict[str, Any], ignored_task_id_list: Optional[List[str]] = None,
    ):
        self.annofab_service = database.annofab_service
        self.annofab_facade = AnnofabApiFacade(database.annofab_service)
        self.database = database
        self.task_query_param = task_query_param
        self.ignored_task_id_list = ignored_task_id_list

        self.project_id = self.database.project_id
        self._update_annotaion_specs()
        self.project_title = self.annofab_service.api.get_project(self.project_id)[0]["title"]

    def _get_worktime_statistics(self) -> List[WorktimeStatistics]:
        """
        タスク作業時間集計を取得
        """
        if self._worktime_statistics is not None:
            return self._worktime_statistics
        else:
            tmp_worktime_statistics = self.annofab_service.wrapper.get_worktime_statistics(self.project_id)
            worktime_statistics: List[WorktimeStatistics] = [
                WorktimeStatistics.from_dict(e) for e in tmp_worktime_statistics  # type: ignore
            ]
            self._worktime_statistics = worktime_statistics
            return worktime_statistics

    def _get_account_statistics(self) -> List[ProjectAccountStatistics]:
        """
        ユーザー別タスク集計を取得
        """
        if self._account_statistics is not None:
            return self._account_statistics
        else:
            content: List[Any] = self.annofab_service.api.get_account_statistics(self.project_id)[0]
            account_statistics = [
                ProjectAccountStatisticsHistory.from_dict(e)  # type: ignore
                for e in content
            ]
            self._account_statistics = account_statistics
            return account_statistics

    def _get_task_list(self) -> List[Task]:
        """
        self.task_listを返す。Noneならば、self.task_list, self.task_id_listを設定する。
        """
        if self._task_list is not None:
            return self._task_list
        else:
            task_list = self.database.read_tasks_from_checkpoint()
            self._task_list = task_list
            return self._task_list

    def _get_inspections_dict(self) -> Dict[str, Dict[InputDataId, List[Inspection]]]:
        if self._inspections_dict is not None:
            return self._inspections_dict
        else:
            task_id_list = [t["task_id"] for t in self._get_task_list()]
            self._inspections_dict = self.database.read_inspections_from_json(task_id_list)
            return self._inspections_dict

    def _get_annotations_dict(self) -> AnnotationDict:
        if self._annotations_dict is not None:
            return self._annotations_dict
        else:
            task_list = self._get_task_list()
            self._annotations_dict = self.database.read_annotation_summary(task_list, self._create_annotation_summary)
            return self._annotations_dict

    def _get_labor_list(self) -> List[Dict[str, Any]]:
        if self._labor_list is not None:
            return self._labor_list
        else:
            labor_list = self.database.read_labor_list_from_checkpoint()
            self._labor_list = labor_list
            return self._labor_list

    def _create_annotation_summary(self, annotation_list: List[SimpleAnnotationDetail]) -> Dict[str, Any]:
        annotation_summary = {}
        annotation_summary["total_count"] = len(annotation_list)

        # labelごとのアノテーション数を算出
        for label_name in self.label_dict.values():
            annotation_count = 0
            key = f"label_{label_name}"
            annotation_count += len([e for e in annotation_list if e.label == label_name])
            annotation_summary[key] = annotation_count

        return annotation_summary

    @staticmethod
    def operator_is_changed_by_phase(task_history_list: List[TaskHistory], phase: TaskPhase) -> bool:
        """
        フェーズ内の作業者が途中で変わったかどうか

        Args:
            task_history_list: タスク履歴List
            phase: フェーズ

        Returns:
            Trueならばフェーズ内の作業者が途中で変わった
        """
        account_id_list = [
            e["account_id"] for e in task_history_list if TaskPhase(e["phase"]) == phase and e["account_id"] is not None
        ]
        return len(set(account_id_list)) >= 2

    @staticmethod
    def _inspection_condition(inspection_arg, exclude_reply: bool, only_error_corrected: bool):
        """
        対象の検査コメントかどうかの判定
        Args:
            inspection_arg:
            exclude_reply:
            only_error_corrected:

        Returns:

        """
        exclude_reply_flag = True
        if exclude_reply:
            exclude_reply_flag = inspection_arg["parent_inspection_id"] is None

        only_error_corrected_flag = True
        if only_error_corrected:
            only_error_corrected_flag = inspection_arg["status"] == InspectionStatus.ERROR_CORRECTED.value

        return exclude_reply_flag and only_error_corrected_flag

    def _get_user_id(self, account_id: Optional[str]) -> Optional[str]:
        """
        プロジェクトメンバのuser_idを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        if account_id is None:
            return None

        member = self.annofab_facade.get_organization_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["user_id"]
        else:
            return account_id

    def _get_username(self, account_id: Optional[str]) -> Optional[str]:
        """
        プロジェクトメンバのusernameを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        if account_id is None:
            return None

        member = self.annofab_facade.get_organization_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["username"]
        else:
            return account_id

    def _get_biography(self, account_id: Optional[str]) -> Optional[str]:
        """
        ユーザのbiographyを取得する。存在しないメンバであればNoneを返す。
        """
        if account_id is None:
            return None

        member = self.annofab_facade.get_organization_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["biography"]
        else:
            return None

    def _update_annotaion_specs(self):
        logger.debug("annofab_service.api.get_annotation_specs()")
        annotaion_specs = self.annofab_service.api.get_annotation_specs(self.project_id)[0]
        self.inspection_phrases_dict = self.get_inspection_phrases_dict(annotaion_specs["inspection_phrases"])
        self.label_dict = self.get_labels_dict(annotaion_specs["labels"])

        logger.debug("annofab_service.wrapper.get_all_project_members()")
        self.project_members_dict = self._get_project_members_dict()

    def _get_project_members_dict(self) -> Dict[str, Any]:
        project_members_dict = {}

        project_members = self.annofab_service.wrapper.get_all_project_members(self.project_id)
        for member in project_members:
            project_members_dict[member["account_id"]] = member
        return project_members_dict

    @staticmethod
    def get_labels_dict(labels) -> Dict[str, str]:
        """
        ラベル情報を設定する
        Returns:
            key: label_id, value: label_name(en)

        """
        label_dict = {}

        for e in labels:
            label_id = e["label_id"]
            messages_list = e["label_name"]["messages"]
            label_name = [m["message"] for m in messages_list if m["lang"] == "en-US"][0]

            label_dict[label_id] = label_name

        return label_dict

    @staticmethod
    def get_inspection_phrases_dict(inspection_phrases) -> Dict[str, str]:
        """
        定型指摘情報を取得
        Returns:
            定型指摘の辞書(key: id, value: 定型コメント(ja))

        """

        inspection_phrases_dict = {}

        for e in inspection_phrases:
            inspection_id = e["id"]
            messages_list = e["text"]["messages"]
            inspection_text = [m["message"] for m in messages_list if m["lang"] == "ja-JP"][0]

            inspection_phrases_dict[inspection_id] = inspection_text

        return inspection_phrases_dict

    def create_inspection_df(self, exclude_reply: bool = True, only_error_corrected: bool = True):
        """
        検査コメント一覧から、検査コメント用のdataframeを作成する。
        新たに追加した列は、"commenter_user_id","label_name"である.
        Args:
            exclude_reply: 返信コメント（「対応完了しました」など）を除く
            only_error_corrected: 「修正済」のコメントのみ。指摘はあったが、修正不要の場合は除外される。

        Returns:
            検査コメント一覧

        """

        master_task_list = self._get_task_list()
        inspections_dict = self._get_inspections_dict()

        all_inspection_list = []

        for task in master_task_list:
            task_id = task["task_id"]
            if task_id not in inspections_dict:
                continue

            input_data_dict = inspections_dict[task_id]
            for inspection_list in input_data_dict.values():

                # 検査コメントを絞り込む
                filtered_inspection_list = [
                    e for e in inspection_list if self._inspection_condition(e, exclude_reply, only_error_corrected)
                ]

                for inspection in filtered_inspection_list:
                    commenter_account_id = inspection["commenter_account_id"]
                    inspection["commenter_user_id"] = self._get_user_id(commenter_account_id)
                    inspection["commenter_username"] = self._get_username(commenter_account_id)

                    # inspection_phrases_dict に存在しないkeyを取得する可能性があるので、dict.getを用いる
                    inspection["phrases_name"] = [
                        self.inspection_phrases_dict.get(key) for key in inspection["phrases"]
                    ]

                    inspection["label_name"] = None
                    if inspection["label_id"] is not None:
                        inspection["label_name"] = self.label_dict.get(inspection["label_id"])

                all_inspection_list.extend(filtered_inspection_list)

        df = pd.DataFrame(all_inspection_list)
        return df

    def _set_first_phase_from_task_history(
        self, task: Task, task_history: Optional[TaskHistory], column_prefix: str
    ) -> Task:
        """
        最初のフェーズに関する情報をTask情報に設定する。

        Args:
            task:
            task_history:
            column_prefix:

        Returns:

        """
        if task_history is None:
            task.update(
                {
                    f"{column_prefix}_account_id": None,
                    f"{column_prefix}_user_id": None,
                    f"{column_prefix}_username": None,
                    f"{column_prefix}_started_datetime": None,
                    f"{column_prefix}_worktime_hour": 0,
                }
            )
        else:
            account_id = task_history["account_id"]
            task.update(
                {
                    f"{column_prefix}_account_id": account_id,
                    f"{column_prefix}_user_id": self._get_user_id(account_id),
                    f"{column_prefix}_username": self._get_username(account_id),
                    f"{column_prefix}_started_datetime": task_history["started_datetime"],
                    f"{column_prefix}_worktime_hour": isoduration_to_hour(
                        task_history["accumulated_labor_time_milliseconds"]
                    ),
                }
            )

        return task

    @staticmethod
    def _get_first_operator_worktime(task_histories: List[TaskHistory], account_id: str) -> float:
        """
        対象ユーザが担当したフェーズの合計作業時間を取得する。

        Args:
            task_histories:
            account_id: 対象】ユーザのaccount_id

        Returns:
            作業時間

        """
        return sum(
            [
                isoduration_to_hour(e["accumulated_labor_time_milliseconds"])
                for e in task_histories
                if e["account_id"] == account_id
            ]
        )

    @staticmethod
    def _acceptance_is_skipped(task_histories: List[TaskHistory]) -> bool:
        task_history_index_list = get_task_history_index_skipped_acceptance(task_histories)
        if len(task_history_index_list) == 0:
            return False

        # スキップされた履歴より後に受入フェーズがなければ、受入がスキップされたタスクとみなす
        # ただし、スキップされた履歴より後で、「アノテーション一覧で修正された」受入フェーズがある場合（account_id is None）は、スキップされた受入とみなす。
        last_task_history_index = task_history_index_list[-1]
        return (
            more_itertools.first_true(
                task_histories[last_task_history_index + 1 :],
                pred=lambda e: e["phase"] == TaskPhase.ACCEPTANCE.value and e["account_id"] is not None,
            )
            is None
        )

    @staticmethod
    def _inspection_is_skipped(task_histories: List[TaskHistory]) -> bool:
        task_history_index_list = get_task_history_index_skipped_inspection(task_histories)
        if len(task_history_index_list) == 0:
            return False

        # スキップされた履歴より後に検査フェーズがなければ、検査がスキップされたタスクとみなす
        last_task_history_index = task_history_index_list[-1]
        return (
            more_itertools.first_true(
                task_histories[last_task_history_index + 1 :], pred=lambda e: e["phase"] == TaskPhase.INSPECTION.value
            )
            is None
        )

    def set_task_histories(self, task: Task, task_histories: List[TaskHistory]):
        """
        タスク履歴関係の情報を設定する
        """

        def diff_days(ended_key: str, started_key: str) -> Optional[float]:
            if task[ended_key] is not None and task[started_key] is not None:
                delta = dateutil.parser.parse(task[ended_key]) - dateutil.parser.parse(task[started_key])
                return delta.total_seconds() / 3600 / 24
            else:
                return None

        annotation_histories = [e for e in task_histories if e["phase"] == TaskPhase.ANNOTATION.value]
        inspection_histories = [e for e in task_histories if e["phase"] == TaskPhase.INSPECTION.value]
        acceptance_histories = [e for e in task_histories if e["phase"] == TaskPhase.ACCEPTANCE.value]

        # 最初の教師付情報を設定する
        first_annotation_history = annotation_histories[0] if len(annotation_histories) > 0 else None
        self._set_first_phase_from_task_history(task, first_annotation_history, column_prefix="first_annotation")

        # 最初の検査情報を設定する
        first_inspection_history = inspection_histories[0] if len(inspection_histories) > 0 else None
        self._set_first_phase_from_task_history(task, first_inspection_history, column_prefix="first_inspection")

        # 最初の受入情報を設定する
        first_acceptance_history = acceptance_histories[0] if len(acceptance_histories) > 0 else None
        self._set_first_phase_from_task_history(task, first_acceptance_history, column_prefix="first_acceptance")

        task["annotation_worktime_hour"] = sum(
            [
                annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"])
                for e in annotation_histories
            ]
        )
        task["inspection_worktime_hour"] = sum(
            [
                annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"])
                for e in inspection_histories
            ]
        )
        task["acceptance_worktime_hour"] = sum(
            [
                annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"])
                for e in acceptance_histories
            ]
        )

        # 最初の教師者が担当した履歴の合計作業時間を取得する。
        # 担当者変更がなければ、"annotation_worktime_hour"と"first_annotation_worktime_hour"は同じ値
        task["first_annotator_worktime_hour"] = (
            self._get_first_operator_worktime(annotation_histories, first_annotation_history["account_id"])
            if first_annotation_history is not None
            else 0
        )

        task["first_inspector_worktime_hour"] = (
            self._get_first_operator_worktime(inspection_histories, first_inspection_history["account_id"])
            if first_inspection_history is not None
            else 0
        )
        task["first_acceptor_worktime_hour"] = (
            self._get_first_operator_worktime(acceptance_histories, first_acceptance_history["account_id"])
            if first_acceptance_history is not None
            else 0
        )

        task["sum_worktime_hour"] = sum(
            [annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) for e in task_histories]
        )

        task["number_of_rejections_by_inspection"] = get_number_of_rejections(
            task["histories_by_phase"], TaskPhase.INSPECTION
        )
        task["number_of_rejections_by_acceptance"] = get_number_of_rejections(
            task["histories_by_phase"], TaskPhase.ACCEPTANCE
        )

        # 受入完了日時を設定
        if task["phase"] == TaskPhase.ACCEPTANCE.value and task["status"] == TaskStatus.COMPLETE.value:
            assert len(acceptance_histories) > 0, f"len(acceptance_histories) is 0"
            task["task_completed_datetime"] = acceptance_histories[-1]["ended_datetime"]
        else:
            task["task_completed_datetime"] = None

        task["diff_days_to_first_inspection_started"] = diff_days(
            "first_inspection_started_datetime", "first_annotation_started_datetime"
        )
        task["diff_days_to_first_acceptance_started"] = diff_days(
            "first_acceptance_started_datetime", "first_annotation_started_datetime"
        )

        task["diff_days_to_task_completed"] = diff_days("task_completed_datetime", "first_annotation_started_datetime")

        # 抜取検査/抜取受入で、検査/受入がスキップされたか否か
        task["acceptance_is_skipped"] = self._acceptance_is_skipped(task_histories)
        task["inspection_is_skipped"] = self._inspection_is_skipped(task_histories)
        task["annotator_is_changed"] = self.operator_is_changed_by_phase(task_histories, TaskPhase.ANNOTATION)
        task["inspector_is_changed"] = self.operator_is_changed_by_phase(task_histories, TaskPhase.INSPECTION)
        task["acceptor_is_changed"] = self.operator_is_changed_by_phase(task_histories, TaskPhase.ACCEPTANCE)

        return task

    @staticmethod
    def _get_task_from_task_id(task_list: List[Task], task_id: str) -> Optional[Task]:
        return more_itertools.first_true(task_list, pred=lambda e: e["task_id"] == task_id)

    def create_task_history_df(self) -> pd.DataFrame:
        """
        タスク履歴の一覧のDataFrameを出力する。

        Returns:

        """
        task_histories_dict = self.database.read_task_histories_from_checkpoint()
        task_list = self._get_task_list()

        all_task_history_list = []
        for task_id, task_history_list in task_histories_dict.items():
            task = self._get_task_from_task_id(task_list, task_id)
            if task is None:
                continue

            for history in task_history_list:
                account_id = history["account_id"]
                history["user_id"] = self._get_user_id(account_id)
                history["username"] = self._get_username(account_id)
                history["biography"] = self._get_biography(account_id)
                history["worktime_hour"] = annofabcli.utils.isoduration_to_hour(
                    history["accumulated_labor_time_milliseconds"]
                )
                # task statusがあると分析しやすいので追加する
                history["task_status"] = task["status"]
                all_task_history_list.append(history)

        df = pd.DataFrame(all_task_history_list)
        return df

    def create_task_df(self) -> pd.DataFrame:
        """
        タスク一覧からdataframeを作成する。
        新たに追加した列は、user_id, annotation_count, inspection_count,
            first_annotation_user_id, first_annotation_started_datetime,
            annotation_worktime_hour, inspection_worktime_hour, acceptance_worktime_hour, sum_worktime_hour
        """

        def set_annotation_info(arg_task):
            total_annotation_count = 0

            input_data_id_list = arg_task["input_data_id_list"]
            input_data_dict = annotations_dict[arg_task["task_id"]]

            for input_data_id in input_data_id_list:
                total_annotation_count += input_data_dict[input_data_id]["total_count"]

            arg_task["annotation_count"] = total_annotation_count

        def set_inspection_info(arg_task):
            # 指摘枚数
            inspection_count = 0
            # 指摘された画像枚数
            input_data_count_of_inspection = 0

            input_data_dict = inspections_dict.get(arg_task["task_id"])
            if input_data_dict is not None:
                for inspection_list in input_data_dict.values():
                    # 検査コメントを絞り込む
                    filtered_inspection_list = [
                        e
                        for e in inspection_list
                        if self._inspection_condition(e, exclude_reply=True, only_error_corrected=True)
                    ]
                    inspection_count += len(filtered_inspection_list)
                    if len(filtered_inspection_list) > 0:
                        input_data_count_of_inspection += 1

            arg_task["inspection_count"] = inspection_count
            arg_task["input_data_count_of_inspection"] = input_data_count_of_inspection

        logger.info(f"execute `create_task_df` function")
        tasks = self._get_task_list()
        task_histories_dict = self.database.read_task_histories_from_checkpoint()
        inspections_dict = self._get_inspections_dict()
        annotations_dict = self._get_annotations_dict()

        for task in tasks:
            task_id = task["task_id"]
            task_histories = task_histories_dict[task_id]

            account_id = task["account_id"]
            task["user_id"] = self._get_user_id(account_id)
            task["username"] = self._get_username(account_id)

            task["input_data_count"] = len(task["input_data_id_list"])
            # number_of_rejections は非推奨な情報なので、削除する
            task.pop("number_of_rejections", None)

            self.set_task_histories(task, task_histories)
            set_annotation_info(task)
            set_inspection_info(task)

        df = pd.DataFrame(tasks)
        # dictが含まれたDataFrameをbokehでグラフ化するとErrorが発生するので、dictを含む列を削除する
        # https://github.com/bokeh/bokeh/issues/9620
        # また不要な列も削除する
        df = df.drop(["histories_by_phase", "project_id"], axis=1)
        return df

    def create_task_for_annotation_df(self):
        """
        アノテーションラベルごとのアノテーション数を表示したタスク一覧を、取得する。
        アノテーションラベルのアノテーション数を格納した列名は、アノテーションラベルの日本語名になる。
        """

        tasks = self._get_task_list()
        annotations_dict = self._get_annotations_dict()

        task_list = []
        for task in tasks:
            task_id = task["task_id"]
            input_data_dict = annotations_dict[task_id]
            new_task = {}
            for key in ["task_id", "phase", "status"]:
                new_task[key] = task[key]

            new_task["input_data_count"] = len(task["input_data_id_list"])
            input_data_id_list = task["input_data_id_list"]

            for label_name in self.label_dict.values():
                annotation_count = 0
                for input_data_id in input_data_id_list:
                    annotation_summary = input_data_dict[input_data_id]
                    annotation_count += annotation_summary[f"label_{label_name}"]

                new_task[f"label_{label_name}"] = annotation_count

            task_list.append(new_task)

        df = pd.DataFrame(task_list)
        return df

    @staticmethod
    def create_dataframe_by_date_user(task_df: pd.DataFrame) -> pd.DataFrame:
        """
        日毎、ユーザごとの情報を出力する。

        Args:
            task_df:

        Returns:

        """
        new_df = task_df
        new_df["first_annotation_started_date"] = new_df["first_annotation_started_datetime"].map(
            lambda e: datetime_to_date(e) if e is not None else None
        )
        new_df["task_count"] = 1  # 集計用

        # first_annotation_user_id と first_annotation_usernameの両方を指定している理由：
        # first_annotation_username を取得するため
        group_obj = new_df.groupby(
            ["first_annotation_started_date", "first_annotation_user_id", "first_annotation_username"], as_index=False,
        )
        sum_df = group_obj[
            [
                "first_annotation_worktime_hour",
                "annotation_worktime_hour",
                "inspection_worktime_hour",
                "acceptance_worktime_hour",
                "sum_worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
                "inspection_count",
            ]
        ].sum()

        sum_df["first_annotation_worktime_minute/annotation_count"] = (
            sum_df["first_annotation_worktime_hour"] * 60 / sum_df["annotation_count"]
        )
        sum_df["annotation_worktime_minute/annotation_count"] = (
            sum_df["annotation_worktime_hour"] * 60 / sum_df["annotation_count"]
        )
        sum_df["inspection_worktime_minute/annotation_count"] = (
            sum_df["inspection_worktime_hour"] * 60 / sum_df["annotation_count"]
        )
        sum_df["acceptance_worktime_minute/annotation_count"] = (
            sum_df["acceptance_worktime_hour"] * 60 / sum_df["annotation_count"]
        )
        sum_df["inspection_count/annotation_count"] = sum_df["inspection_count"] / sum_df["annotation_count"]

        sum_df["first_annotation_worktime_minute/input_data_count"] = (
            sum_df["first_annotation_worktime_hour"] * 60 / sum_df["input_data_count"]
        )
        sum_df["annotation_worktime_minute/input_data_count"] = (
            sum_df["annotation_worktime_hour"] * 60 / sum_df["input_data_count"]
        )
        sum_df["inspection_worktime_minute/input_data_count"] = (
            sum_df["inspection_worktime_hour"] * 60 / sum_df["input_data_count"]
        )
        sum_df["acceptance_worktime_minute/input_data_count"] = (
            sum_df["acceptance_worktime_hour"] * 60 / sum_df["input_data_count"]
        )
        sum_df["inspection_count/input_data_count"] = sum_df["inspection_count"] / sum_df["annotation_count"]

        return sum_df

    def create_member_df(self, task_df: pd.DataFrame) -> pd.DataFrame:
        """
        プロジェクトメンバ一覧の情報
        """

        task_histories_dict = self.database.read_task_histories_from_checkpoint()

        member_dict = {}
        for account_id, member in self.project_members_dict.items():
            new_member = copy.deepcopy(member)
            new_member.update(
                {
                    # 初回のアノテーションに関わった個数（タスクの教師付担当者は変更されない前提）
                    "task_count_of_first_annotation": 0,
                    "input_data_count_of_first_annotation": 0,
                    "annotation_count_of_first_annotation": 0,
                    "inspection_count_of_first_annotation": 0,
                    # 関わった作業時間
                    "annotation_worktime_hour": 0,
                    "inspection_worktime_hour": 0,
                    "acceptance_worktime_hour": 0,
                }
            )
            member_dict[account_id] = new_member

        for _, row_task in task_df.iterrows():
            task_id = row_task["task_id"]

            task_histories = task_histories_dict[task_id]

            # 初回のアノテーションに関わった個数
            if row_task["first_annotation_account_id"] is not None:
                first_annotation_account_id = row_task["first_annotation_account_id"]
                if first_annotation_account_id in member_dict:
                    member = member_dict[first_annotation_account_id]
                    member["task_count_of_first_annotation"] += 1
                    member["input_data_count_of_first_annotation"] += row_task["input_data_count"]
                    member["annotation_count_of_first_annotation"] += row_task["annotation_count"]
                    member["inspection_count_of_first_annotation"] += row_task["inspection_count"]

            # 関わった作業時間を記載
            for history in task_histories:
                account_id = history["account_id"]
                if account_id is None:
                    continue

                phase = history["phase"]
                worktime_hour = annofabcli.utils.isoduration_to_hour(history["accumulated_labor_time_milliseconds"])
                if history["account_id"] in member_dict:
                    member = member_dict[history["account_id"]]
                    member[f"{phase}_worktime_hour"] += worktime_hour

        member_list = []
        for account_id, member in member_dict.items():
            member_list.append(member)

        df = pd.DataFrame(member_list)
        return df

    def create_account_statistics_df(self):
        """
        メンバごと、日ごとの作業時間を、統計情報APIから取得する。
        """

        account_statistics = self.database.read_account_statistics_from_checkpoint()

        all_histories = []
        for account_info in account_statistics:

            account_id = account_info["account_id"]
            histories = account_info["histories"]

            member_info = self.project_members_dict.get(account_id)

            for history in histories:
                history["worktime_hour"] = annofabcli.utils.isoduration_to_hour(history["worktime"])
                history["account_id"] = account_id
                history["user_id"] = self._get_user_id(account_id)
                history["username"] = self._get_username(account_id)
                history["biography"] = self._get_biography(account_id)

                if member_info is not None:
                    history["member_role"] = member_info["member_role"]

            all_histories.extend(histories)

        df = pd.DataFrame(all_histories)
        return df

    @staticmethod
    def create_cumulative_df_by_user(account_statistics_df: pd.DataFrame) -> pd.DataFrame:
        """
        アカウントごとの作業時間に対して、累積作業時間を追加する。
        Args:
            account_statistics_df: アカウントごとの作業時間用DataFrame

        Returns:

        """
        # 教師付の開始時刻でソートして、indexを更新する
        df = account_statistics_df.sort_values(["account_id", "date"]).reset_index(drop=True)
        groupby_obj = df.groupby("account_id")
        df["cumulative_worktime_hour"] = groupby_obj["worktime_hour"].cumsum()
        return df

    @staticmethod
    def create_cumulative_df_overall(task_df: pd.DataFrame) -> pd.DataFrame:
        """
        1回目の教師付開始日でソートして、累積値を算出する。

        Args:
            task_df: タスク一覧のDataFrame. 列が追加される
        """
        # 教師付の開始時刻でソートして、indexを更新する
        df = task_df.sort_values(["first_annotation_started_datetime"]).reset_index(drop=True)
        # タスクの累計数を取得するために設定する
        df["task_count"] = 1

        # 作業時間の累積値
        df["cumulative_annotation_worktime_hour"] = df["annotation_worktime_hour"].cumsum()
        df["cumulative_inspection_worktime_hour"] = df["inspection_worktime_hour"].cumsum()
        df["cumulative_acceptance_worktime_hour"] = df["acceptance_worktime_hour"].cumsum()
        df["cumulative_sum_worktime_hour"] = df["sum_worktime_hour"].cumsum()

        # タスク完了数、差し戻し数など
        df["cumulative_inspection_count"] = df["inspection_count"].cumsum()
        df["cumulative_annotation_count"] = df["annotation_count"].cumsum()
        df["cumulative_input_data_count"] = df["input_data_count"].cumsum()
        df["cumulative_task_count"] = df["task_count"].cumsum()
        df["cumulative_number_of_rejections"] = df["number_of_rejections"].cumsum()
        df["cumulative_number_of_rejections_by_inspection"] = df["number_of_rejections_by_inspection"].cumsum()
        df["cumulative_number_of_rejections_by_acceptance"] = df["number_of_rejections_by_acceptance"].cumsum()

        # 元に戻す
        df = df.drop(["task_count"], axis=1)
        return df

    @staticmethod
    def create_cumulative_df_by_first_annotator(task_df: pd.DataFrame) -> pd.DataFrame:
        """
        最初のアノテーション作業の開始時刻の順にソートして、教師付者に関する累計値を算出する
        Args:
            task_df: タスク一覧のDataFrame. 列が追加される
        """
        # 教師付の開始時刻でソートして、indexを更新する
        df = task_df.sort_values(["first_annotation_account_id", "first_annotation_started_datetime"]).reset_index(
            drop=True
        )
        # タスクの累計数を取得するために設定する
        df["task_count"] = 1
        # 教師付の作業者でgroupby
        groupby_obj = df.groupby("first_annotation_account_id")

        # 作業時間の累積値
        df["cumulative_annotation_worktime_hour"] = groupby_obj["annotation_worktime_hour"].cumsum()
        df["cumulative_acceptance_worktime_hour"] = groupby_obj["acceptance_worktime_hour"].cumsum()
        df["cumulative_inspection_worktime_hour"] = groupby_obj["inspection_worktime_hour"].cumsum()
        df["cumulative_first_annotation_worktime_hour"] = groupby_obj["first_annotation_worktime_hour"].cumsum()

        # タスク完了数、差し戻し数など
        df["cumulative_inspection_count"] = groupby_obj["inspection_count"].cumsum()
        df["cumulative_annotation_count"] = groupby_obj["annotation_count"].cumsum()
        df["cumulative_input_data_count"] = groupby_obj["input_data_count"].cumsum()
        df["cumulative_task_count"] = groupby_obj["task_count"].cumsum()
        df["cumulative_number_of_rejections"] = groupby_obj["number_of_rejections"].cumsum()
        df["cumulative_number_of_rejections_by_inspection"] = groupby_obj["number_of_rejections_by_inspection"].cumsum()
        df["cumulative_number_of_rejections_by_acceptance"] = groupby_obj["number_of_rejections_by_acceptance"].cumsum()

        # 元に戻す
        df = df.drop(["task_count"], axis=1)
        return df

    @staticmethod
    def create_cumulative_df_by_first_inspector(task_df: pd.DataFrame) -> pd.DataFrame:
        """
        最初の検査作業の開始時刻の順にソートして、累計値を算出する
        Args:
            task_df: タスク一覧のDataFrame. 列が追加される
        """

        df = task_df.sort_values(["first_inspection_account_id", "first_inspection_started_datetime"]).reset_index(
            drop=True
        )
        # タスクの累計数を取得するために設定する
        df["task_count"] = 1
        # 教師付の作業者でgroupby
        groupby_obj = df.groupby("first_inspection_account_id")

        # 作業時間の累積値
        df["cumulative_annotation_worktime_hour"] = groupby_obj["annotation_worktime_hour"].cumsum()
        df["cumulative_acceptance_worktime_hour"] = groupby_obj["acceptance_worktime_hour"].cumsum()
        df["cumulative_inspection_worktime_hour"] = groupby_obj["inspection_worktime_hour"].cumsum()
        df["cumulative_first_inspection_worktime_hour"] = groupby_obj["first_inspection_worktime_hour"].cumsum()

        # タスク完了数、差し戻し数など
        df["cumulative_inspection_count"] = groupby_obj["inspection_count"].cumsum()
        df["cumulative_annotation_count"] = groupby_obj["annotation_count"].cumsum()
        df["cumulative_input_data_count"] = groupby_obj["input_data_count"].cumsum()
        df["cumulative_task_count"] = groupby_obj["task_count"].cumsum()
        df["cumulative_number_of_rejections"] = groupby_obj["number_of_rejections"].cumsum()
        df["cumulative_number_of_rejections_by_inspection"] = groupby_obj["number_of_rejections_by_inspection"].cumsum()
        df["cumulative_number_of_rejections_by_acceptance"] = groupby_obj["number_of_rejections_by_acceptance"].cumsum()

        # 元に戻す
        df = df.drop(["task_count"], axis=1)
        return df

    @staticmethod
    def create_cumulative_df_by_first_acceptor(task_df: pd.DataFrame) -> pd.DataFrame:
        """
        最初の受入作業の開始時刻の順にソートして、累計値を算出する
        Args:
            task_df: タスク一覧のDataFrame. 列が追加される
        """

        df = task_df.sort_values(["first_acceptance_account_id", "first_acceptance_started_datetime"]).reset_index(
            drop=True
        )
        # タスクの累計数を取得するために設定する
        df["task_count"] = 1
        groupby_obj = df.groupby("first_acceptance_account_id")

        # 作業時間の累積値
        df["cumulative_acceptance_worktime_hour"] = groupby_obj["acceptance_worktime_hour"].cumsum()
        df["cumulative_first_acceptance_worktime_hour"] = groupby_obj["first_acceptance_worktime_hour"].cumsum()

        # タスク完了数、差し戻し数など
        df["cumulative_inspection_count"] = groupby_obj["inspection_count"].cumsum()
        df["cumulative_annotation_count"] = groupby_obj["annotation_count"].cumsum()
        df["cumulative_input_data_count"] = groupby_obj["input_data_count"].cumsum()
        df["cumulative_task_count"] = groupby_obj["task_count"].cumsum()
        df["cumulative_number_of_rejections"] = groupby_obj["number_of_rejections"].cumsum()
        df["cumulative_number_of_rejections_by_inspection"] = groupby_obj["number_of_rejections_by_inspection"].cumsum()
        df["cumulative_number_of_rejections_by_acceptance"] = groupby_obj["number_of_rejections_by_acceptance"].cumsum()

        # 元に戻す
        df = df.drop(["task_count"], axis=1)
        return df

    def create_worktime_per_image_df(self, aggregation_by: AggregationBy, phase: TaskPhase) -> pd.DataFrame:
        """
        画像１枚あたり/タスク１個あたりの作業時間を算出する。
        行方向に日付, 列方向にメンバを並べる

        Args:
            aggregation_by: 集計単位（画像1枚あたり or タスク１個あたり）
            phase: 対象のフェーズ

        Returns:
            DataFrame
        """

        worktime_statistics = self._get_worktime_statistics()

        worktime_info_list = []
        for elm in worktime_statistics:
            worktime_info: Dict[str, Any] = {"date": elm.date}
            for account_info in elm.accounts:
                stat_list = getattr(account_info, aggregation_by.value)
                stat_item: Optional[WorktimeStatisticsItem] = first_true(stat_list, pred=lambda e: e.phase == phase)
                if stat_item is not None:
                    worktime_info[account_info.account_id] = isoduration_to_hour(stat_item.average)
                else:
                    worktime_info[account_info.account_id] = 0

            worktime_info_list.append(worktime_info)

        df = pd.DataFrame(worktime_info_list)
        # acount_idをusernameに変更する
        columns = {
            col: self._get_username(col) for col in df.columns if col != "date"  # pylint: disable=not-an-iterable
        }
        return df.rename(columns=columns).fillna(0)

    @staticmethod
    def create_annotation_count_ratio_df(task_history_df: pd.DataFrame, task_df: pd.DataFrame) -> pd.DataFrame:
        """
        task_id, phase, (phase_index), user_idの作業時間比から、アノテーション数などの生産量を求める

        Args:

        Returns:

        """
        annotation_count_dict = {
            row["task_id"]: {
                "annotation_count": row["annotation_count"],
                "input_data_count": row["input_data_count"],
                "inspection_comment_count": row["inspection_count"],
            }
            for _, row in task_df.iterrows()
        }

        def get_inspection_comment_count(row) -> float:
            task_id = row.name[0]
            inspection_comment_count = annotation_count_dict[task_id]["inspection_comment_count"]
            return row["worktime_ratio_by_task"] * inspection_comment_count

        def get_annotation_count(row) -> float:
            task_id = row.name[0]
            annotation_count = annotation_count_dict[task_id]["annotation_count"]
            return row["worktime_ratio_by_task"] * annotation_count

        def get_input_data_count(row) -> float:
            task_id = row.name[0]
            annotation_count = annotation_count_dict[task_id]["input_data_count"]
            return row["worktime_ratio_by_task"] * annotation_count

        group_obj = task_history_df.groupby(["task_id", "phase", "phase_stage", "user_id"]).agg(
            {"worktime_hour": "sum"}
        )
        group_obj["worktime_ratio_by_task"] = group_obj.groupby(level=["task_id", "phase", "phase_stage"]).apply(
            lambda e: e / float(e.sum())
        )
        group_obj["annotation_count"] = group_obj.apply(get_annotation_count, axis="columns")
        group_obj["input_data_count"] = group_obj.apply(get_input_data_count, axis="columns")
        group_obj["pointed_out_inspection_comment_count"] = group_obj.apply(
            get_inspection_comment_count, axis="columns"
        )

        new_df = group_obj.reset_index()
        new_df["pointed_out_inspection_comment_count"] = new_df["pointed_out_inspection_comment_count"] * new_df[
            "phase"
        ].apply(lambda e: 1 if e == TaskPhase.ANNOTATION.value else 0)
        return new_df

    @staticmethod
    def _get_phase_list(columns: List[str]) -> List[str]:
        phase_list = [TaskPhase.ANNOTATION.value, TaskPhase.INSPECTION.value, TaskPhase.ACCEPTANCE.value]
        if TaskPhase.INSPECTION.value not in columns:
            phase_list.remove(TaskPhase.INSPECTION.value)

        if TaskPhase.ACCEPTANCE.value not in columns:
            phase_list.remove(TaskPhase.ACCEPTANCE.value)

        return phase_list

    @staticmethod
    def create_productivity_per_user_from_aw_time(
        df_task_history: pd.DataFrame, df_labor: pd.DataFrame, df_worktime_ratio: pd.DataFrame
    ) -> pd.DataFrame:
        """
        AnnoWorkの実績時間から、作業者ごとに生産性を算出する。

        Returns:

        """
        df_agg_task_history = df_task_history.pivot_table(
            values="worktime_hour", columns="phase", index="user_id", aggfunc=numpy.sum
        ).fillna(0)

        if len(df_labor) > 0:
            df_agg_labor = df_labor.pivot_table(values="worktime_result_hour", index="user_id", aggfunc=numpy.sum)
            df = df_agg_task_history.join(df_agg_labor)
        else:
            df = df_agg_task_history
            df["worktime_result_hour"] = 0

        phase_list = Table._get_phase_list(list(df.columns))

        df = df[["worktime_result_hour"] + phase_list]
        df.columns = pd.MultiIndex.from_tuples(
            [("annowork_worktime_hour", "sum")] + [("annofab_worktime_hour", phase) for phase in phase_list]
        )

        df[("annofab_worktime_hour", "sum")] = df[[("annofab_worktime_hour", phase) for phase in phase_list]].sum(
            axis=1
        )

        df_agg_production = df_worktime_ratio.pivot_table(
            values=[
                "worktime_ratio_by_task",
                "input_data_count",
                "annotation_count",
                "pointed_out_inspection_comment_count",
            ],
            columns="phase",
            index="user_id",
            aggfunc=numpy.sum,
        ).fillna(0)

        df_agg_production.rename(columns={"worktime_ratio_by_task": "task_count"}, inplace=True)
        df = df.join(df_agg_production)

        for phase in phase_list:
            # AnnoFab時間の比率
            df[("annofab_worktime_ratio", phase)] = (
                df[("annofab_worktime_hour", phase)] / df[("annofab_worktime_hour", "sum")]
            )
            # AnnoFab時間の比率から、Annowork時間を予測する
            df[("prediction_annowork_worktime_hour", phase)] = (
                df[("annowork_worktime_hour", "sum")] * df[("annofab_worktime_ratio", phase)]
            )

            # 生産性を算出
            df[("annofab_worktime/input_data_count", phase)] = (
                df[("annofab_worktime_hour", phase)] / df[("input_data_count", phase)]
            )
            df[("annowork_worktime/input_data_count", phase)] = (
                df[("prediction_annowork_worktime_hour", phase)] / df[("input_data_count", phase)]
            )

            df[("annofab_worktime/annotation_count", phase)] = (
                df[("annofab_worktime_hour", phase)] / df[("annotation_count", phase)]
            )
            df[("annowork_worktime/annotation_count", phase)] = (
                df[("prediction_annowork_worktime_hour", phase)] / df[("annotation_count", phase)]
            )

        phase = TaskPhase.ANNOTATION.value
        df[("pointed_out_inspection_comment_count/annotation_count", phase)] = (
            df[("pointed_out_inspection_comment_count", phase)] / df[("annotation_count", phase)]
        )
        df[("pointed_out_inspection_comment_count/input_data_count", phase)] = (
            df[("pointed_out_inspection_comment_count", phase)] / df[("input_data_count", phase)]
        )

        # 不要な列を削除する
        tmp_phase_list = copy.deepcopy(phase_list)
        tmp_phase_list.remove(TaskPhase.ANNOTATION.value)
        df = df.drop([("pointed_out_inspection_comment_count", phase) for phase in tmp_phase_list], axis=1)

        # ユーザ情報を取得
        df_user = df_task_history.groupby("user_id").first()[["username", "biography"]]
        df_user.columns = pd.MultiIndex.from_tuples([("username", ""), ("biography", "")])
        df = df.join(df_user)
        df[("user_id", "")] = df.index

        return df

    def create_labor_df(self) -> pd.DataFrame:
        """
        労務管理 DataFrameを生成する。情報を出力する。

        """

        def add_user_info(d: Dict[str, Any]) -> Dict[str, Any]:
            account_id = d["account_id"]
            d["user_id"] = self._get_user_id(account_id)
            d["username"] = self._get_username(account_id)
            d["biography"] = self._get_biography(account_id)
            return d

        labor_list = self._get_labor_list()
        return pd.DataFrame([add_user_info(e) for e in labor_list])
