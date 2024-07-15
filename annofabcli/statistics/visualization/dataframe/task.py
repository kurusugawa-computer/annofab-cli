from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import annofabapi
import bokeh
import bokeh.layouts
import bokeh.palettes
import numpy
import pandas
import pytz

from annofabcli.common.utils import print_csv
from annofabcli.statistics.histogram import create_histogram_figure, get_sub_title_from_series
from annofabcli.statistics.visualization.dataframe.annotation_count import AnnotationCount
from annofabcli.statistics.visualization.dataframe.inspection_comment_count import InspectionCommentCount
from annofabcli.task.list_all_tasks_added_task_history import AddingAdditionalInfoToTask

logger = logging.getLogger(__name__)

BIN_COUNT = 20
"""ヒストグラムのビンの個数"""


class Task:
    """
    'タスクlist.csv'に該当するデータフレームをラップしたクラス

    `project_id`,`task_id`のペアがユニークなキーです。
    """

    @staticmethod
    def _duplicated_keys(df: pandas.DataFrame) -> bool:
        """
        DataFrameに重複したキーがあるかどうかを返します。
        """
        duplicated = df.duplicated(subset=["project_id", "task_id"])
        return duplicated.any()

    @classmethod
    def required_columns_exist(cls, df: pandas.DataFrame) -> bool:
        """
        必須の列が存在するかどうかを返します。

        Returns:
            必須の列が存在するかどうか
        """
        return len(set(cls.columns()) - set(df.columns)) == 0

    def __init__(self, df: pandas.DataFrame) -> None:
        if self._duplicated_keys(df):
            logger.warning("引数`df`に重複したキー（project_id, task_id）が含まれています。")

        if not self.required_columns_exist(df):
            raise ValueError(f"引数`df`には、{self.columns()}の列が必要です。 :: {df.columns=}")

        self.df = df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @classmethod
    def columns(cls) -> list[str]:
        return [
            # 基本的な情報
            "project_id",
            "task_id",
            "phase",
            "phase_stage",
            "status",
            "number_of_rejections_by_inspection",
            "number_of_rejections_by_acceptance",
            # タスク作成時
            "created_datetime",
            # 1回目の教師付フェーズ
            "first_annotation_user_id",
            "first_annotation_username",
            "first_annotation_worktime_hour",
            "first_annotation_started_datetime",
            # 1回目の検査フェーズ
            "first_inspection_user_id",
            "first_inspection_username",
            "first_inspection_worktime_hour",
            "first_inspection_started_datetime",
            # 1回目の受入フェーズ
            "first_acceptance_user_id",
            "first_acceptance_username",
            "first_acceptance_worktime_hour",
            "first_acceptance_started_datetime",
            # 最後の受入
            "first_acceptance_completed_datetime",
            # 作業時間に関する内容
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            # 個数
            "input_data_count",
            "annotation_count",
            "inspection_comment_count",
            "inspection_comment_count_in_inspection_phase",
            "inspection_comment_count_in_acceptance_phase",
            # タスクの状態
            "inspection_is_skipped",
            "acceptance_is_skipped",
        ]

    @classmethod
    def from_api_content(
        cls,
        tasks: list[dict[str, Any]],
        task_histories: dict[str, list[dict[str, Any]]],
        inspection_comment_count: InspectionCommentCount,
        annotation_count: AnnotationCount,
        project_id: str,
        annofab_service: annofabapi.Resource,
    ) -> Task:
        """
        APIから取得した情報と、DataFrameのラッパーからインスタンスを生成します。

        Args:
            tasks: APIから取得したタスク情報
            task_histories: APIから取得したタスク履歴情報
            inspection_comment_count: 検査コメント数を格納したDataFrameのラッパー
            annotation_count: アノテーション数を格納したDataFrameのラッパー
            annofab_service: TODO `AddingAdditionalInfoToTask`を修正したら、この引数を削除する。このクラスからAPIに直接アクセスさせたくない。

        """

        adding_obj = AddingAdditionalInfoToTask(annofab_service, project_id=project_id)

        for task in tasks:
            adding_obj.add_additional_info_to_task(task)

            task_id = task["task_id"]
            if task_id not in task_histories:
                logger.warning(f"引数`task_histories`の中にtask_id='{task_id}'に対応するタスク履歴がありません。 :: {project_id=}")

            sub_task_histories = task_histories.get(task_id, [])

            # タスク履歴から取得できる付加的な情報を追加する
            adding_obj.add_task_history_additional_info_to_task(task, sub_task_histories)

        df = pandas.DataFrame(tasks)
        if len(df) == 0:
            return cls.empty()

        # dictが含まれたDataFrameをbokehでグラフ化するとErrorが発生するので、dictを含む列を削除する
        # https://github.com/bokeh/bokeh/issues/9620
        df = df.drop(["histories_by_phase"], axis=1)

        df = df.merge(annotation_count.df, on=["project_id", "task_id"], how="left")
        df = df.merge(inspection_comment_count.df, on=["project_id", "task_id"], how="left")
        df = df.fillna(
            {
                "inspection_comment_count": 0,
                "inspection_comment_count_in_inspection_phase": 0,
                "inspection_comment_count_in_acceptance_phase": 0,
                "annotation_count": 0,
            }
        )
        return cls(df)

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0

    @classmethod
    def empty(cls) -> Task:
        """空のデータフレームを持つインスタンスを生成します。"""

        bool_columns = {
            "inspection_is_skipped",
            "acceptance_is_skipped",
        }

        string_columns = {
            "project_id",
            "task_id",
            "phase",
            "phase_stage",
            "status",
            "created_datetime",
            "first_annotation_user_id",
            "first_annotation_username",
            "first_annotation_started_datetime",
            "first_inspection_user_id",
            "first_inspection_username",
            "first_inspection_started_datetime",
            "first_acceptance_user_id",
            "first_acceptance_username",
            "first_acceptance_started_datetime",
            "first_acceptance_completed_datetime",
        }

        numeric_columns = set(cls.columns()) - bool_columns - string_columns
        df_dtype: dict[str, str] = {}
        for col in numeric_columns:
            df_dtype[col] = "float"
        for col in string_columns:
            df_dtype[col] = "string"
        for col in bool_columns:
            df_dtype[col] = "boolean"

        df = pandas.DataFrame(columns=cls.columns()).astype(df_dtype)
        return cls(df)

    @classmethod
    def from_csv(cls, csv_file: Path) -> Task:
        df = pandas.read_csv(str(csv_file))
        return cls(df)

    @staticmethod
    def merge(*obj: Task) -> Task:
        """
        複数のインスタンスをマージします。

        Notes:
            pandas.DataFrameのインスタンス生成のコストを減らすため、複数の引数を受け取れるようにした。
        """
        df_list = [task.df for task in obj]
        df_merged = pandas.concat(df_list)
        return Task(df_merged)

    def plot_histogram_of_worktime(
        self,
        output_file: Path,
    ) -> None:
        """作業時間に関する情報をヒストグラムでプロットする。

        Args:
            output_file (Path): [description]
        """
        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")
        df = self.df
        histogram_list = [
            {
                "title": "教師付作業時間",
                "column": "annotation_worktime_hour",
            },
            {
                "title": "検査作業時間",
                "column": "inspection_worktime_hour",
            },
            {
                "title": "受入作業時間",
                "column": "acceptance_worktime_hour",
            },
            {"title": "総作業時間", "column": "worktime_hour"},
        ]

        figure_list = []

        decimals = 2
        for histogram in histogram_list:
            column = histogram["column"]
            title = histogram["title"]
            sub_title = get_sub_title_from_series(df[column], decimals=decimals)

            hist, bin_edges = numpy.histogram(df[column], bins=BIN_COUNT)
            fig = create_histogram_figure(hist, bin_edges, x_axis_label="作業時間[hour]", y_axis_label="タスク数", title=title, sub_title=sub_title)
            figure_list.append(fig)

        # 自動検査したタスクを除外して、検査時間をグラフ化する
        df_ignore_inspection_skipped = df.query("inspection_worktime_hour.notnull() and not inspection_is_skipped")
        sub_title = get_sub_title_from_series(df_ignore_inspection_skipped["inspection_worktime_hour"], decimals=decimals)

        hist, bin_edges = numpy.histogram(df_ignore_inspection_skipped["inspection_worktime_hour"], bins=BIN_COUNT)
        figure_list.append(
            create_histogram_figure(
                hist,
                bin_edges,
                x_axis_label="作業時間[hour]",
                y_axis_label="タスク数",
                title="検査作業時間(自動検査されたタスクを除外)",
                sub_title=sub_title,
            )
        )

        df_ignore_acceptance_skipped = df.query("acceptance_worktime_hour.notnull() and not acceptance_is_skipped")
        sub_title = get_sub_title_from_series(df_ignore_acceptance_skipped["acceptance_worktime_hour"], decimals=decimals)
        hist, bin_edges = numpy.histogram(df_ignore_acceptance_skipped["acceptance_worktime_hour"], bins=BIN_COUNT)

        figure_list.append(
            create_histogram_figure(
                hist,
                bin_edges,
                x_axis_label="作業時間[hour]",
                y_axis_label="タスク数",
                title="受入作業時間(自動受入されたタスクを除外)",
                sub_title=sub_title,
            )
        )

        bokeh_obj = bokeh.layouts.gridplot(figure_list, ncols=3)  # type: ignore[arg-type]
        output_file.parent.mkdir(exist_ok=True, parents=True)
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=output_file.stem)
        bokeh.plotting.save(bokeh_obj)
        logger.debug(f"'{output_file}'を出力しました。")

    def plot_histogram_of_others(
        self,
        output_file: Path,
    ) -> None:
        """アノテーション数や、検査コメント数など、作業時間以外の情報をヒストグラムで表示する。

        Args:
            output_file (Path): [description]
        """

        def diff_days(s1: pandas.Series, s2: pandas.Series) -> pandas.Series:
            dt1 = pandas.to_datetime(s1, format="ISO8601")
            dt2 = pandas.to_datetime(s2, format="ISO8601")

            # タイムゾーンを指定している理由::
            # すべてがNaNのseriesをdatetimeに変換すると、型にタイムゾーンが指定されない。
            # その状態で加算すると、`TypeError: DatetimeArray subtraction must have the same timezones or no timezones`というエラーが発生するため  # noqa: E501
            if not isinstance(dt1.dtype, pandas.DatetimeTZDtype):
                dt1 = dt1.dt.tz_localize(pytz.FixedOffset(540))
            if not isinstance(dt2.dtype, pandas.DatetimeTZDtype):
                dt2 = dt2.dt.tz_localize(pytz.FixedOffset(540))

            return (dt1 - dt2).dt.total_seconds() / 3600 / 24

        if not self._validate_df_for_output(output_file):
            return

        logger.debug(f"{output_file} を出力します。")
        df = self.df.copy()

        df["diff_days_to_first_inspection_started"] = diff_days(df["first_inspection_started_datetime"], df["first_annotation_started_datetime"])
        df["diff_days_to_first_acceptance_started"] = diff_days(df["first_acceptance_started_datetime"], df["first_annotation_started_datetime"])

        df["diff_days_to_first_acceptance_completed"] = diff_days(df["first_acceptance_completed_datetime"], df["first_annotation_started_datetime"])

        histogram_list = [
            {"column": "annotation_count", "x_axis_label": "アノテーション数", "title": "アノテーション数"},
            {"column": "input_data_count", "x_axis_label": "入力データ数", "title": "入力データ数"},
            {"column": "inspection_comment_count", "x_axis_label": "検査コメント数", "title": "検査コメント数"},
            # 経過日数
            {
                "column": "diff_days_to_first_inspection_started",
                "x_axis_label": "最初の検査を着手するまでの日数",
                "title": "最初の検査を着手するまでの日数",
            },
            {
                "column": "diff_days_to_first_acceptance_started",
                "x_axis_label": "最初の受入を着手するまでの日数",
                "title": "最初の受入を着手するまでの日数",
            },
            {
                "column": "diff_days_to_first_acceptance_completed",
                "x_axis_label": "初めて受入完了状態になるまでの日数",
                "title": "初めて受入完了状態になるまでの日数",
            },
            # 差し戻し回数
            {
                "column": "number_of_rejections_by_inspection",
                "x_axis_label": "検査フェーズでの差し戻し回数",
                "title": "検査フェーズでの差し戻し回数",
            },
            {
                "column": "number_of_rejections_by_acceptance",
                "x_axis_label": "受入フェーズでの差し戻し回数",
                "title": "受入フェーズでの差し戻し回数",
            },
        ]

        figure_list = []

        for histogram in histogram_list:
            column = histogram["column"]
            title = histogram["title"]
            x_axis_label = histogram["x_axis_label"]
            ser = df[column].dropna()
            sub_title = get_sub_title_from_series(ser, decimals=2)
            hist, bin_edges = numpy.histogram(ser, bins=BIN_COUNT)
            fig = create_histogram_figure(hist, bin_edges, x_axis_label=x_axis_label, y_axis_label="タスク数", title=title, sub_title=sub_title)
            figure_list.append(fig)

        bokeh_obj = bokeh.layouts.gridplot(figure_list, ncols=4)  # type: ignore[arg-type]
        output_file.parent.mkdir(exist_ok=True, parents=True)
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=output_file.stem)
        bokeh.plotting.save(bokeh_obj)
        logger.debug(f"'{output_file}'を出力しました。")

    def to_csv(self, output_file: Path) -> None:
        """
        タスク一覧をCSVで出力する
        """

        if not self._validate_df_for_output(output_file):
            return

        print_csv(self.df[self.columns()], str(output_file))

    def mask_user_info(
        self,
        to_replace_for_user_id: Optional[dict[str, str]] = None,
        to_replace_for_username: Optional[dict[str, str]] = None,
    ) -> Task:
        """
        引数から渡された情報を元に、インスタンス変数`df`内のユーザー情報をマスクして、新しいインスタンスを返します。

        Args:
            to_replace_for_user_id: user_idを置換するためのdict。keyは置換前のuser_id, valueは置換後のuser_id。
            to_replace_for_username: usernameを置換するためのdict。keyは置換前のusername, valueは置換後のusername。

        """
        to_replace_info = {
            "first_annotation_user_id": to_replace_for_user_id,
            "first_inspection_user_id": to_replace_for_user_id,
            "first_acceptance_user_id": to_replace_for_user_id,
            "first_annotation_username": to_replace_for_username,
            "first_inspection_username": to_replace_for_username,
            "first_acceptance_username": to_replace_for_username,
        }
        df = self.df.replace(to_replace_info)
        return Task(df)
