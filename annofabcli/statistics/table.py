import logging
from typing import Any, Dict, List, Optional

import dateutil
import more_itertools
import pandas
from annofabapi.models import InputDataId, Inspection, InspectionStatus, Task, TaskHistory, TaskPhase, TaskStatus
from annofabapi.utils import (
    get_number_of_rejections,
    get_task_history_index_skipped_acceptance,
    get_task_history_index_skipped_inspection,
)

import annofabcli
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import isoduration_to_hour
from annofabcli.statistics.database import Database

logger = logging.getLogger(__name__)


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

    _task_list: Optional[List[Task]] = None
    _inspections_dict: Optional[Dict[str, Dict[InputDataId, List[Inspection]]]] = None
    _task_histories_dict: Optional[Dict[str, List[TaskHistory]]] = None

    def __init__(
        self,
        database: Database,
        ignored_task_id_list: Optional[List[str]] = None,
    ):
        self.annofab_service = database.annofab_service
        self.annofab_facade = AnnofabApiFacade(database.annofab_service)
        self.database = database
        self.ignored_task_id_list = ignored_task_id_list

        self.project_id = self.database.project_id
        self.project_members_dict = self._get_project_members_dict()

        self.project_title = self.annofab_service.api.get_project(self.project_id)[0]["title"]

    def _get_task_list(self) -> List[Task]:
        """
        self.task_listを返す。Noneならば、self.task_list, self.task_id_listを設定する。
        """
        if self._task_list is not None:
            return self._task_list
        else:
            task_list = self.database.read_tasks_from_json()
            self._task_list = task_list
            return self._task_list

    def _get_inspections_dict(self) -> Dict[str, Dict[InputDataId, List[Inspection]]]:
        if self._inspections_dict is not None:
            return self._inspections_dict
        else:
            task_id_list = [t["task_id"] for t in self._get_task_list()]
            self._inspections_dict = self.database.read_inspections_from_json(task_id_list)
            return self._inspections_dict

    def _get_task_histories_dict(self) -> Dict[str, List[TaskHistory]]:
        if self._task_histories_dict is not None:
            return self._task_histories_dict
        else:
            task_id_list = [t["task_id"] for t in self._get_task_list()]
            self._task_histories_dict = self.database.read_task_histories_from_json(task_id_list)
            return self._task_histories_dict

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
            e["account_id"]
            for e in task_history_list
            if TaskPhase(e["phase"]) == phase
            and e["account_id"] is not None
            and isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) > 0
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
        プロジェクトメンバのuser_idを返す。
        """
        if account_id is None:
            return None

        member = self.annofab_facade.get_project_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["user_id"]
        else:
            return None

    def _get_username(self, account_id: Optional[str]) -> Optional[str]:
        """
        プロジェクトメンバのusernameを返す。
        """
        if account_id is None:
            return None

        member = self.annofab_facade.get_project_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["username"]
        else:
            return None

    def _get_biography(self, account_id: Optional[str]) -> Optional[str]:
        """
        ユーザのbiographyを取得する。存在しないメンバであればNoneを返す。
        """
        if account_id is None:
            return None

        member = self.annofab_facade.get_project_member_from_account_id(self.project_id, account_id)
        if member is not None:
            return member["biography"]
        else:
            return None

    def _get_project_members_dict(self) -> Dict[str, Any]:
        project_members_dict = {}

        project_members = self.annofab_service.wrapper.get_all_project_members(self.project_id)
        for member in project_members:
            project_members_dict[member["account_id"]] = member
        return project_members_dict

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

        def filter_histories(arg_task_histories: List[TaskHistory], phase: TaskPhase) -> List[TaskHistory]:
            """指定したフェーズで作業したタスク履歴を絞り込む。"""
            return [
                e
                for e in arg_task_histories
                if (
                    e["phase"] == phase.value
                    and e["account_id"] is not None
                    and annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) > 0
                )
            ]

        annotation_histories = filter_histories(task_histories, TaskPhase.ANNOTATION)
        inspection_histories = filter_histories(task_histories, TaskPhase.INSPECTION)
        acceptance_histories = filter_histories(task_histories, TaskPhase.ACCEPTANCE)

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
        # APIで取得した 'number_of_rejections' は非推奨で、number_of_rejections_by_inspection/acceptanceと矛盾する場合があるので、書き換える
        task["number_of_rejections"] = (
            task["number_of_rejections_by_inspection"] + task["number_of_rejections_by_acceptance"]
        )

        # 受入完了日時を設定
        if task["phase"] == TaskPhase.ACCEPTANCE.value and task["status"] == TaskStatus.COMPLETE.value:
            assert len(task_histories) > 0
            task["task_completed_datetime"] = task_histories[-1]["ended_datetime"]
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

    def create_task_history_df(self) -> pandas.DataFrame:
        """
        タスク履歴の一覧のDataFrameを出力する。

        Returns:

        """
        task_histories_dict = self._get_task_histories_dict()
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

        df = pandas.DataFrame(all_task_history_list)
        if len(df) == 0:
            logger.warning("タスク履歴の件数が0件です。")
            return pandas.DataFrame()
        else:
            return df

    def create_task_df(self) -> pandas.DataFrame:
        """
        タスク一覧からdataframeを作成する。
        新たに追加した列は、user_id, annotation_count, inspection_count,
            first_annotation_user_id, first_annotation_started_datetime,
            annotation_worktime_hour, inspection_worktime_hour, acceptance_worktime_hour, sum_worktime_hour
        """

        def set_input_data_info_for_movie(arg_task):
            input_data_id_list = arg_task["input_data_id_list"]
            input_data = input_data_dict.get(input_data_id_list[0])
            if input_data is None:
                logger.warning(f"task_id={arg_task['task_id']} に含まれる入力データID {input_data_id_list[0]} は存在しません。")
                arg_task["input_duration_seconds"] = None
                return
            arg_task["input_duration_seconds"] = input_data.input_duration_seconds

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

        tasks = self._get_task_list()
        task_histories_dict = self._get_task_histories_dict()
        inspections_dict = self._get_inspections_dict()
        annotations_dict = self.database.get_annotation_count_by_task()
        input_data_dict = self.database.read_input_data_from_json()

        for task in tasks:
            task_id = task["task_id"]
            task_histories = task_histories_dict.get(task_id, [])

            account_id = task["account_id"]
            task["user_id"] = self._get_user_id(account_id)
            task["username"] = self._get_username(account_id)
            task["input_data_count"] = len(task["input_data_id_list"])

            self.set_task_histories(task, task_histories)

            task["annotation_count"] = annotations_dict.get(task_id, 0)
            set_inspection_info(task)
            set_input_data_info_for_movie(task)

        df = pandas.DataFrame(tasks)
        if len(df) > 0:
            # dictが含まれたDataFrameをbokehでグラフ化するとErrorが発生するので、dictを含む列を削除する
            # https://github.com/bokeh/bokeh/issues/9620
            df = df.drop(["histories_by_phase"], axis=1)
            return df
        else:
            logger.warning(f"タスク一覧が0件です。")
            return pandas.DataFrame()

    @staticmethod
    def create_gradient_df(task_df: pandas.DataFrame) -> pandas.DataFrame:
        """
        生産量あたりの指標を算出する

        """
        task_df["annotation_worktime_hour/annotation_count"] = (
            task_df["annotation_worktime_hour"] / task_df["annotation_count"]
        )
        task_df["inspection_count/annotation_count"] = task_df["inspection_count"] / task_df["annotation_count"]
        task_df["number_of_rejections/annotation_count"] = task_df["number_of_rejections"] / task_df["annotation_count"]

        task_df["inspection_worktime_hour/annotation_count"] = (
            task_df["inspection_worktime_hour"] / task_df["annotation_count"]
        )
        task_df["acceptance_worktime_hour/annotation_count"] = (
            task_df["acceptance_worktime_hour"] / task_df["annotation_count"]
        )
        return task_df

    @staticmethod
    def create_annotation_count_ratio_df(
        task_history_df: pandas.DataFrame, task_df: pandas.DataFrame
    ) -> pandas.DataFrame:
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
                "rejected_count": row["number_of_rejections"],
            }
            for _, row in task_df.iterrows()
        }

        def get_inspection_comment_count(row) -> float:
            task_id = row.name[0]
            inspection_comment_count = annotation_count_dict[task_id]["inspection_comment_count"]
            return row["worktime_ratio_by_task"] * inspection_comment_count

        def get_rejected_count(row) -> float:
            task_id = row.name[0]
            rejected_count = annotation_count_dict[task_id]["rejected_count"]
            return row["worktime_ratio_by_task"] * rejected_count

        def get_annotation_count(row) -> float:
            task_id = row.name[0]
            annotation_count = annotation_count_dict[task_id]["annotation_count"]
            result = row["worktime_ratio_by_task"] * annotation_count
            return result

        def get_input_data_count(row) -> float:
            task_id = row.name[0]
            annotation_count = annotation_count_dict[task_id]["input_data_count"]
            return row["worktime_ratio_by_task"] * annotation_count

        if len(task_df) == 0:
            logger.warning("タスク一覧が0件です。")
            return pandas.DataFrame()

        group_obj = task_history_df.groupby(["task_id", "phase", "phase_stage", "user_id"]).agg(
            {"worktime_hour": "sum"}
        )
        if len(group_obj) == 0:
            logger.warning(f"タスク履歴情報に作業しているタスクがありませんでした。タスク履歴全件ファイルが更新されていない可能性があります。")
            return pandas.DataFrame(
                columns=[
                    "task_id",
                    "phase",
                    "phase_stage",
                    "user_id",
                    "worktime_hour",
                    "worktime_ratio_by_task",
                    "annotation_count",
                    "input_data_count",
                    "pointed_out_inspection_comment_count",
                    "rejected_count",
                ]
            )

        group_obj["worktime_ratio_by_task"] = group_obj.groupby(level=["task_id", "phase", "phase_stage"]).apply(
            lambda e: e / float(e.sum())
        )
        group_obj["annotation_count"] = group_obj.apply(get_annotation_count, axis="columns")
        group_obj["input_data_count"] = group_obj.apply(get_input_data_count, axis="columns")
        group_obj["pointed_out_inspection_comment_count"] = group_obj.apply(
            get_inspection_comment_count, axis="columns"
        )
        group_obj["rejected_count"] = group_obj.apply(get_rejected_count, axis="columns")
        new_df = group_obj.reset_index()
        new_df["pointed_out_inspection_comment_count"] = new_df["pointed_out_inspection_comment_count"] * new_df[
            "phase"
        ].apply(lambda e: 1 if e == TaskPhase.ANNOTATION.value else 0)
        new_df["rejected_count"] = new_df["rejected_count"] * new_df["phase"].apply(
            lambda e: 1 if e == TaskPhase.ANNOTATION.value else 0
        )
        return new_df

    def create_labor_df(self, df_labor: Optional[pandas.DataFrame] = None) -> pandas.DataFrame:
        """
        労務管理 DataFrameを生成する。情報を出力する。

        Args:
            df_labor: 指定されれば、account_idに紐づくユーザ情報を添付する。そうでなければ、webapiから労務管理情報を取得する。
        """
        if df_labor is None:
            labor_list = self.database.get_labor_list(self.project_id)
            df_labor = pandas.DataFrame(labor_list)

        if len(df_labor) == 0:
            return pandas.DataFrame(
                columns=["date", "account_id", "user_id", "username", "biography", "actual_worktime_hour"]
            )

        df_user = pandas.DataFrame(self.project_members_dict.values())[
            ["account_id", "user_id", "username", "biography"]
        ]

        df = df_labor.merge(df_user, how="left", on="account_id")
        return df
