import copy
import logging
from typing import Any, Dict, List, Optional, Set, Tuple  # pylint: disable=unused-import

import dateutil.parser
import pandas as pd
from annofabapi.models import Annotation, InputDataId, Inspection, Task, TaskHistory, TaskId

import annofabcli
from annofabcli.statistics.database import Database

logger = logging.getLogger(__name__)


class Table:
    """
    Databaseから取得した情報を元にPandas DataFrameを生成するクラス
    チェックポイントファイルがあること前提
    """

    #############################################
    # Field
    #############################################

    label_dict: Dict[str, str] = None
    """label_idとその名前の辞書"""

    inspection_phrases_dict: Dict[str, str] = None
    """定型指摘IDとそのコメント"""

    project_members_dict: Dict[str, Any] = None
    """account_idとプロジェクトメンバ情報"""

    #############################################
    # Private
    #############################################

    task_id_list: List[TaskId] = None
    task_list: List[Task] = None
    inspections_dict: Dict[TaskId, Dict[InputDataId, List[Inspection]]] = None
    annotations_dict: Dict[TaskId, Dict[InputDataId, List[Annotation]]] = None

    def __init__(self, database: Database, task_query_param: Dict[str, Any],
                 ignored_task_id_list: Optional[List[TaskId]] = None):
        self.annofab_service = database.annofab_service
        self.database = database
        self.task_query_param = task_query_param
        self.ignored_task_id_list = ignored_task_id_list

        self.project_id = self.database.project_id
        self._update_annotaion_specs()
        self.project_title = self.annofab_service.api.get_project(self.project_id)[0]['title']

        # self.custom_count_annotations_info = visualize_statistics.config.custom_count_annotations_info.get(self.project_id, {})

    def _get_task_list(self) -> List[Task]:
        """
        self.task_listを返す。Noneならば、self.task_list, self.task_id_listを設定する。
        """
        if self.task_list is not None:
            return self.task_list
        else:
            task_list = self.database.read_tasks_from_json(self.task_query_param, self.ignored_task_id_list)
            self.task_list = task_list
            return self.task_list

    def _get_inspections_dict(self) -> Dict[TaskId, Dict[InputDataId, List[Inspection]]]:
        if self.inspections_dict is not None:
            return self.inspections_dict
        else:
            task_id_list = [t["task_id"] for t in self.task_list]
            self.inspections_dict = self.database.read_inspections_from_json(task_id_list)
            return self.inspections_dict

    def _get_annotations_dict(self) -> Dict[TaskId, Dict[InputDataId, List[Annotation]]]:
        if self.annotations_dict is not None:
            return self.annotations_dict
        else:
            task_list = self._get_task_list()
            self.annotations_dict = self.database.read_annotations_from_full_annotion_dir(task_list)
            return self.annotations_dict

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
        self.project_members_dict = self.get_project_members_dict()

    @staticmethod
    def _get_acceptance_count_and_histories(task_histories: List[TaskHistory]) -> List[Tuple[int, TaskHistory]]:
        """
        受入で差し戻しごとにグループ分けする。
        """

        new_list: List[Tuple[int, TaskHistory]] = []
        rejections_by_phase = 0
        for i, history in enumerate(task_histories):
            if history['phase'] == 'annotation':
                if i - 1 >= 0 and task_histories[i - 1]['phase'] == 'acceptance':
                    rejections_by_phase += 1

            elm = rejections_by_phase, history
            new_list.append(elm)

        return new_list

    def get_project_members_dict(self):
        project_members_dict = {}

        project_members = self.annofab_service.wrapper.get_all_project_members(self.project_id)
        for member in project_members:
            project_members_dict[member["account_id"]] = member
        return project_members_dict

    @staticmethod
    def get_labels_dict(labels):
        """
        ラベル情報を設定する
        Returns:
            key: label_id, value: label_name(ja)

        """
        label_dict = {}

        for e in labels:
            label_id = e["label_id"]
            messages_list = e["label_name"]["messages"]
            label_name = [m["message"] for m in messages_list if m["lang"] == "ja-JP"][0]

            label_dict[label_id] = label_name

        return label_dict

    @staticmethod
    def get_inspection_phrases_dict(inspection_phrases):
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
            for input_data_id, inspection_list in input_data_dict.items():

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

                    annotation_id = inspection["annotation_id"]
                    inspection["label_name"] = None
                    if inspection["label_id"] is not None:
                        inspection["label_name"] = self.label_dict.get(inspection["label_id"])

                all_inspection_list.extend(filtered_inspection_list)

        df = pd.DataFrame(all_inspection_list)
        return df

    def create_task_df(self) -> pd.DataFrame:
        """
        タスク一覧からdataframeを作成する。
        新たに追加した列は、user_id, annotation_count, inspection_count,
            first_annotation_user_id, first_annotation_started_datetime,
            annotation_worktime_hour, inspection_worktime_hour, acceptance_worktime_hour, sum_worktime_hour
        """
        def get_rejections_by_phase(phase, arg_task_histories) -> int:
            """
            phaseごとの差し戻し回数を算出
            """

            rejections_by_phase = 0
            for i, history in enumerate(arg_task_histories):
                if history['phase'] != phase or history['ended_datetime'] is None:
                    continue

                if i + 1 < len(arg_task_histories) and arg_task_histories[i + 1]['phase'] == 'annotation':
                    rejections_by_phase += 1

            return rejections_by_phase

        def set_task_histories(arg_task, arg_task_histories):
            """
            タスク履歴関係の情報を設定する
            """
            annotation_histories = [e for e in arg_task_histories if e["phase"] == "annotation"]
            inspection_histories = [e for e in arg_task_histories if e["phase"] == "inspection"]
            acceptance_histories = [e for e in arg_task_histories if e["phase"] == "acceptance"]

            if len(annotation_histories) > 0:
                first_annotation_history = annotation_histories[0]
                first_annotation_account_id = first_annotation_history["account_id"]
                arg_task["first_annotation_account_id"] = first_annotation_account_id
                arg_task["first_annotation_user_id"] = self._get_user_id(first_annotation_account_id)
                arg_task["first_annotation_username"] = self._get_username(first_annotation_account_id)
                arg_task["first_annotation_started_datetime"] = first_annotation_history["started_datetime"]
                arg_task["first_annotation_worktime_hour"] = annofabcli.utils.isoduration_to_hour(
                    first_annotation_history["accumulated_labor_time_milliseconds"])
            else:
                arg_task["first_annotation_account_id"] = None
                arg_task["first_annotation_user_id"] = None
                arg_task["first_annotation_username"] = None
                arg_task["first_annotation_started_datetime"] = None
                arg_task["first_annotation_worktime_hour"] = 0

            if len(acceptance_histories) > 0:
                for count, history in enumerate(acceptance_histories):
                    arg_task[f"acceptance_username_{count:02d}"] = self._get_username(history["account_id"])
                    arg_task[f"acceptance_worktime_hour_{count:02d}"] = annofabcli.utils.isoduration_to_hour(
                        history['accumulated_labor_time_milliseconds'])

            arg_task["annotation_worktime_hour"] = sum([
                annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"])
                for e in annotation_histories
            ])
            arg_task["inspection_worktime_hour"] = sum([
                annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"])
                for e in inspection_histories
            ])
            arg_task["acceptance_worktime_hour"] = sum([
                annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"])
                for e in acceptance_histories
            ])

            arg_task["sum_worktime_hour"] = sum([
                annofabcli.utils.isoduration_to_hour(e["accumulated_labor_time_milliseconds"])
                for e in arg_task_histories
            ])

            arg_task['number_of_rejections_by_inspection'] = get_rejections_by_phase('inspection', arg_task_histories)
            arg_task['number_of_rejections_by_acceptance'] = get_rejections_by_phase('acceptance', arg_task_histories)

            return arg_task

        def set_annotation_info(arg_task):
            input_data_dict = annotations_dict[arg_task["task_id"]]
            total_annotation_count = 0
            for annotation_list in input_data_dict.values():
                total_annotation_count += len(annotation_list)

            arg_task["annotation_count"] = total_annotation_count

        def set_inspection_info(arg_task):
            # 指摘枚数
            inspection_count = 0
            # 指摘された画像枚数
            input_data_count_of_inspection = 0

            input_data_dict = inspections_dict.get(arg_task["task_id"])
            if input_data_dict is not None:
                for input_data_id, inspection_list in input_data_dict.items():
                    # 検査コメントを絞り込む
                    filtered_inspection_list = [e for e in inspection_list if self._inspection_condition(e, True, True)]
                    inspection_count += len(filtered_inspection_list)
                    if len(filtered_inspection_list) > 0:
                        input_data_count_of_inspection += 1

            arg_task["inspection_count"] = inspection_count
            arg_task["input_data_count_of_inspection"] = input_data_count_of_inspection

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
            task["project_title"] = self.project_title

            task["started_date"] = str(dateutil.parser.parse(
                task["started_datetime"]).date()) if task["started_datetime"] is not None else None
            task["updated_date"] = str(dateutil.parser.parse(
                task["updated_datetime"]).date()) if task["updated_datetime"] is not None else None

            set_task_histories(task, task_histories)
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

            new_task = {}
            for key in ["task_id", "phase", "status"]:
                new_task[key] = task[key]

            new_task["input_data_count"] = len(task["input_data_id_list"])

            input_data_dict = annotations_dict[task_id]
            for label_id, label_name in self.label_dict.items():
                annotation_count = 0
                for annotation_list in input_data_dict.values():
                    annotation_count += len([e for e in annotation_list if e["label_id"] == label_id])

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

        for index, row_task in task_df.iterrows():
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
