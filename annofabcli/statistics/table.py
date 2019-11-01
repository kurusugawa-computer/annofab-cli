import copy
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple  # pylint: disable=unused-import

import dateutil.parser
import pandas as pd
from annofabapi.dataclass.annotation import SimpleAnnotationDetail
from annofabapi.dataclass.statistics import (ProjectAccountStatistics, ProjectAccountStatisticsHistory,
                                             WorktimeStatistics, WorktimeStatisticsItem)
from annofabapi.models import InputDataId, Inspection, Task, TaskHistory, TaskId, TaskPhase
from more_itertools import first_true

import annofabcli
from annofabcli.common.utils import isoduration_to_hour
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

    _task_id_list: Optional[List[TaskId]] = None
    _task_list: Optional[List[Task]] = None
    _inspections_dict: Optional[Dict[TaskId, Dict[InputDataId, List[Inspection]]]] = None
    _annotations_dict: Optional[Dict[TaskId, Dict[InputDataId, Dict[str, Any]]]] = None
    _worktime_statistics: Optional[List[WorktimeStatistics]] = None
    _account_statistics: Optional[List[ProjectAccountStatistics]] = None

    def __init__(self, database: Database, task_query_param: Dict[str, Any],
                 ignored_task_id_list: Optional[List[TaskId]] = None):
        self.annofab_service = database.annofab_service
        self.database = database
        self.task_query_param = task_query_param
        self.ignored_task_id_list = ignored_task_id_list

        self.project_id = self.database.project_id
        self._update_annotaion_specs()
        self.project_title = self.annofab_service.api.get_project(self.project_id)[0]['title']

    def _get_worktime_statistics(self) -> List[WorktimeStatistics]:
        """
        タスク作業時間集計を取得
        """
        if self._worktime_statistics is not None:
            return self._worktime_statistics
        else:
            worktime_statistics = self.annofab_service.wrapper.get_worktime_statistics(self.project_id)
            worktime_statistics = [WorktimeStatistics.from_dict(e) for e in worktime_statistics]
            self._worktime_statistics = worktime_statistics
            return worktime_statistics

    def _get_account_statistics(self) -> List[ProjectAccountStatistics]:
        """
        ユーザー別タスク集計を取得
        """
        if self._account_statistics is not None:
            return self._account_statistics
        else:
            account_statistics, = self.annofab_service.api.get_account_statistics(self.project_id)
            account_statistics = [ProjectAccountStatisticsHistory.from_dict(e) for e in account_statistics]
            self._account_statistics = account_statistics
            return account_statistics

    def _get_task_list(self) -> List[Task]:
        """
        self.task_listを返す。Noneならば、self.task_list, self.task_id_listを設定する。
        """
        if self._task_list is not None:
            return self._task_list
        else:
            task_list = self.database.read_tasks_from_json(self.task_query_param, self.ignored_task_id_list)
            self._task_list = task_list
            return self._task_list

    def _get_inspections_dict(self) -> Dict[TaskId, Dict[InputDataId, List[Inspection]]]:
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
            only_error_corrected_flag = inspection_arg["status"] == "error_corrected"

        return exclude_reply_flag and only_error_corrected_flag

    def _get_user_id(self, account_id):
        """
        プロジェクトメンバのuser_idを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        if account_id is None:
            return None

        if account_id in self.project_members_dict:
            return self.project_members_dict[account_id]["user_id"]
        else:
            return account_id

    def _get_username(self, account_id):
        """
        プロジェクトメンバのusernameを取得する。プロジェクトメンバでなければ、account_idを返す。
        account_idがNoneならばNoneを返す。
        """
        if account_id is None:
            return None

        if account_id in self.project_members_dict:
            return self.project_members_dict[account_id]["username"]
        else:
            return account_id

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

    @staticmethod
    def get_rejections_by_phase(task_histories: List[TaskHistory], phase: TaskPhase) -> int:
        """
        あるphaseでの差し戻し回数を算出

        Args:
            task_histories: タスク履歴
            phase: どのフェーズで差し戻されたか

        Returns:
            差し戻し回数

        """

        rejections_by_phase = 0
        for i, history in enumerate(task_histories):
            if history['phase'] != phase.value or history['ended_datetime'] is None:
                continue

            if i + 1 < len(task_histories) and task_histories[i + 1]['phase'] == TaskPhase.ANNOTATION.value:
                rejections_by_phase += 1

        return rejections_by_phase

    def set_task_histories(self, task: Task, task_histories: List[TaskHistory]):
        """
        タスク履歴関係の情報を設定する
        """
        annotation_histories = [e for e in task_histories if e["phase"] == TaskPhase.ANNOTATION.value]
        inspection_histories = [e for e in task_histories if e["phase"] == TaskPhase.INSPECTION.value]
        acceptance_histories = [e for e in task_histories if e["phase"] == TaskPhase.ACCEPTANCE.value]

        if len(annotation_histories) > 0:
            first_annotation_history = annotation_histories[0]
            first_annotation_account_id = first_annotation_history["account_id"]
            task["first_annotation_account_id"] = first_annotation_account_id
            task["first_annotation_user_id"] = self._get_user_id(first_annotation_account_id)
            task["first_annotation_username"] = self._get_username(first_annotation_account_id)
            task["first_annotation_started_datetime"] = first_annotation_history["started_datetime"]
            task["first_annotation_worktime_hour"] = annofabcli.utils.isoduration_to_hour(
                first_annotation_history["accumulated_labor_time_milliseconds"])
        else:
            task["first_annotation_account_id"] = None
            task["first_annotation_user_id"] = None
            task["first_annotation_username"] = None
            task["first_annotation_started_datetime"] = None
            task["first_annotation_worktime_hour"] = 0

        task["annotation_worktime_hour"] = sum([
            annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) for e in annotation_histories
        ])
        task["inspection_worktime_hour"] = sum([
            annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) for e in inspection_histories
        ])
        task["acceptance_worktime_hour"] = sum([
            annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) for e in acceptance_histories
        ])

        task["sum_worktime_hour"] = sum(
            [annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) for e in task_histories])

        task['number_of_rejections_by_inspection'] = self.get_rejections_by_phase(task_histories, TaskPhase.INSPECTION)
        task['number_of_rejections_by_acceptance'] = self.get_rejections_by_phase(task_histories, TaskPhase.ACCEPTANCE)

        return task

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
                    filtered_inspection_list = [e for e in inspection_list if self._inspection_condition(e, True, True)]
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

            task["started_date"] = str(dateutil.parser.parse(
                task["started_datetime"]).date()) if task["started_datetime"] is not None else None
            task["updated_date"] = str(dateutil.parser.parse(
                task["updated_datetime"]).date()) if task["updated_datetime"] is not None else None

            self.set_task_histories(task, task_histories)
            set_annotation_info(task)
            set_inspection_info(task)

        df = pd.DataFrame(tasks)

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

                new_task[label_name] = annotation_count

            task_list.append(new_task)

        df = pd.DataFrame(task_list)
        return df

    def create_member_df(self, task_df: pd.DataFrame = None) -> pd.DataFrame:
        """
        プロジェクトメンバ一覧の情報
        """

        if task_df is None:
            task_df = self.create_task_df()

        task_histories_dict = self.database.read_task_histories_from_checkpoint()

        member_dict = {}
        for account_id, member in self.project_members_dict.items():
            new_member = copy.deepcopy(member)
            new_member.update({
                # 初回のアノテーションに関わった個数（タスクの教師付担当者は変更されない前提）
                "task_count_of_first_annotation": 0,
                "input_data_count_of_first_annotation": 0,
                "annotation_count_of_first_annotation": 0,
                "inspection_count_of_first_annotation": 0,

                # 関わった作業時間
                "annotation_worktime_hour": 0,
                "inspection_worktime_hour": 0,
                "acceptance_worktime_hour": 0,
            })
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
        メンバごと、日ごとの作業時間
        """

        account_statistics = self.database.read_account_statistics_from_checkpoint()

        all_histories = []
        for account_info in account_statistics:

            account_id = account_info['account_id']
            histories = account_info['histories']

            member_info = self.project_members_dict.get(account_id)

            for history in histories:
                history['worktime_hour'] = annofabcli.utils.isoduration_to_hour(history['worktime'])
                history['account_id'] = account_id
                history['user_id'] = self._get_user_id(account_id)
                history['username'] = self._get_username(account_id)

                if member_info is not None:
                    history['member_role'] = member_info['member_role']

            all_histories.extend(histories)

        df = pd.DataFrame(all_histories)
        return df

    @staticmethod
    def create_cumulative_df(task_df: pd.DataFrame) -> pd.DataFrame:
        """
        最初のアノテーション作業の開始時刻の順にソートして、累計値を算出する
        Args:
            task_df: タスク一覧のDataFrame. 列が追加される
        """
        # 教師付の開始時刻でソートして、indexを更新する
        df = task_df.sort_values(["first_annotation_account_id",
                                  "first_annotation_started_datetime"]).reset_index(drop=True)

        # 教師付の作業者でgroupby
        groupby_obj = df.groupby("first_annotation_account_id")

        # 作業時間の累積値
        df["cumulative_annotation_worktime_hour"] = groupby_obj["annotation_worktime_hour"].cumsum()
        df["cumulative_acceptance_worktime_hour"] = groupby_obj["acceptance_worktime_hour"].cumsum()
        df["cumulative_inspection_worktime_hour"] = groupby_obj["inspection_worktime_hour"].cumsum()

        # タスク完了数、差し戻し数
        df["cumulative_inspection_count"] = groupby_obj["inspection_count"].cumsum()
        df["cumulative_annotation_count"] = groupby_obj["annotation_count"].cumsum()

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
            worktime_info = {"date": elm.date}
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
        columns = {col: self._get_username(col) for col in df.columns if col != "date"}  # pylint: disable=not-an-iterable # noqa: E501
        return df.rename(columns=columns).fillna(0)

    def create_account_statistics_df2(self, account_statistics_value: AccountStatisticsValue) -> pd.DataFrame:
        """
        メンバ別のタスク集計情報を取得する
        行方向に日付, 列方向にメンバを並べる

        Args:
            account_statistics_value: 集計する値

        Returns:
            DataFrame
        """
        def get_value_from_history(his: ProjectAccountStatisticsHistory) -> Any:
            value = getattr(his, account_statistics_value.value)
            if account_statistics_value == AccountStatisticsValue.WORKTIME:
                return isoduration_to_hour(value)
            else:
                return value

        account_statistics = self._get_account_statistics()
        dict_date_account_info: Dict[str, Dict[str, Any]] = {}
        for account_info in account_statistics:
            account_id = account_info.account_id
            for history in account_info.histories:
                date = history.date
                dict_account_info = dict_date_account_info.get(date, default={})
                dict_account_info[account_id] = get_value_from_history(history)
                dict_date_account_info[date] = dict_account_info

        account_info_list = []
        for date, account_info in sorted(dict_date_account_info.items()):
            account_info["date"] = date
            account_info_list.append(account_info)

        df = pd.DataFrame(account_info_list)
        # acount_idをusernameに変更する
        columns = {col: self._get_username(col) for col in df.columns if col != "date"}  # pylint: disable=not-an-iterable # noqa: E501
        return df.rename(columns=columns).fillna(0)
