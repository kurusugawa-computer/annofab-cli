import logging
from typing import Any, Dict, List, Optional

import dateutil
import more_itertools
import pandas
from annofabapi.models import InputDataId, Inspection, InspectionStatus, Task, TaskHistory, TaskPhase

import annofabcli
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import isoduration_to_hour
from annofabcli.statistics.database import Database
from annofabcli.task.list_tasks_added_task_history import AddingAdditionalInfoToTask

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
    ):
        self.annofab_service = database.annofab_service
        self.annofab_facade = AnnofabApiFacade(database.annofab_service)
        self.database = database

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

    @classmethod
    def set_task_histories(cls, task: Task, task_histories: List[TaskHistory]):
        """
        タスク履歴関係の情報を設定する
        """

        def diff_days(ended_key: str, started_key: str) -> Optional[float]:
            if task[ended_key] is not None and task[started_key] is not None:
                delta = dateutil.parser.parse(task[ended_key]) - dateutil.parser.parse(task[started_key])
                return delta.total_seconds() / 3600 / 24
            else:
                return None

        task["worktime_hour"] = sum(
            [annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) for e in task_histories]
        )

        # APIで取得した 'number_of_rejections' は非推奨で、number_of_rejections_by_inspection/acceptanceと矛盾する場合があるので、書き換える
        task["number_of_rejections"] = (
            task["number_of_rejections_by_inspection"] + task["number_of_rejections_by_acceptance"]
        )

        task["diff_days_to_first_inspection_started"] = diff_days(
            "first_inspection_started_datetime", "first_annotation_started_datetime"
        )
        task["diff_days_to_first_acceptance_started"] = diff_days(
            "first_acceptance_started_datetime", "first_annotation_started_datetime"
        )

        task["diff_days_to_first_acceptance_completed"] = diff_days(
            "first_acceptance_completed_datetime", "first_annotation_started_datetime"
        )

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
        新たに追加した列は、user_id, annotation_count, inspection_comment_count,
            first_annotation_user_id, first_annotation_started_datetime,
            annotation_worktime_hour, inspection_worktime_hour, acceptance_worktime_hour, worktime_hour
        """

        def set_input_data_info_for_movie(arg_task):
            input_data_id_list = arg_task["input_data_id_list"]
            input_data = input_data_dict.get(input_data_id_list[0])
            if input_data is None:
                logger.warning(f"task_id={arg_task['task_id']} に含まれる入力データID {input_data_id_list[0]} は存在しません。")
                arg_task["input_duration_seconds"] = None
                return
            arg_task["input_duration_seconds"] = input_data.input_duration_seconds

        def set_inspection_comment_info(arg_task):
            # 指摘枚数
            inspection_comment_count = 0
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
                    inspection_comment_count += len(filtered_inspection_list)
                    if len(filtered_inspection_list) > 0:
                        input_data_count_of_inspection += 1

            arg_task["inspection_comment_count"] = inspection_comment_count

            arg_task["input_data_count_of_inspection"] = input_data_count_of_inspection

        tasks = self._get_task_list()
        task_histories_dict = self._get_task_histories_dict()
        inspections_dict = self._get_inspections_dict()
        annotations_dict = self.database.get_annotation_count_by_task()
        input_data_dict = self.database.read_input_data_from_json()

        adding_obj = AddingAdditionalInfoToTask(self.annofab_service, project_id=self.project_id)

        for task in tasks:

            adding_obj.add_additional_info_to_task(task)

            task_id = task["task_id"]
            task_histories = task_histories_dict.get(task_id, [])

            task["input_data_count"] = len(task["input_data_id_list"])

            # タスク履歴から取得できる付加的な情報を追加する
            adding_obj.add_task_history_additional_info_to_task(task, task_histories)
            self.set_task_histories(task, task_histories)

            task["annotation_count"] = annotations_dict.get(task_id, 0)
            set_inspection_comment_info(task)
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
        task_df["inspection_comment_count/annotation_count"] = (
            task_df["inspection_comment_count"] / task_df["annotation_count"]
        )
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
                "inspection_comment_count": row["inspection_comment_count"],
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

        group_obj = task_history_df.groupby(["task_id", "phase", "phase_stage", "account_id"]).agg(
            {"worktime_hour": "sum"}
        )
        if len(group_obj) == 0:
            logger.warning(f"タスク履歴情報に作業しているタスクがありませんでした。タスク履歴全件ファイルが更新されていない可能性があります。")
            return pandas.DataFrame(
                columns=[
                    "task_id",
                    "phase",
                    "phase_stage",
                    "account_id",
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
