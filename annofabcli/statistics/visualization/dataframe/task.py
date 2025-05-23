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
from bokeh.plotting import figure

from annofabcli.common.bokeh import convert_1d_figure_list_to_2d, create_pretext_from_metadata
from annofabcli.common.utils import print_csv
from annofabcli.statistics.histogram import create_histogram_figure, get_sub_title_from_series
from annofabcli.statistics.visualization.dataframe.annotation_count import AnnotationCount
from annofabcli.statistics.visualization.dataframe.custom_production_volume import CustomProductionVolume
from annofabcli.statistics.visualization.dataframe.input_data_count import InputDataCount
from annofabcli.statistics.visualization.dataframe.inspection_comment_count import InspectionCommentCount
from annofabcli.statistics.visualization.model import ProductionVolumeColumn
from annofabcli.task.list_all_tasks_added_task_history import AddingAdditionalInfoToTask

logger = logging.getLogger(__name__)

BIN_COUNT = 20
"""ヒストグラムのビンの個数"""


class Task:
    """
    'タスクlist.csv'に該当するデータフレームをラップしたクラス

    `project_id`,`task_id`のペアがユニークなキーです。

    Args:
        custom_production_volume_columns: ユーザー独自の生産量を表す列名のlist

    """

    @staticmethod
    def _duplicated_keys(df: pandas.DataFrame) -> bool:
        """
        DataFrameに重複したキーがあるかどうかを返します。
        """
        duplicated = df.duplicated(subset=["project_id", "task_id"])
        return duplicated.any()

    def required_columns_exist(self, df: pandas.DataFrame) -> bool:
        """
        必須の列が存在するかどうかを返します。

        Returns:
            必須の列が存在するかどうか
        """
        return len(set(self.required_columns) - set(df.columns)) == 0

    def missing_required_columns(self, df: pandas.DataFrame) -> list[str]:
        """
        欠損している必須の列名を取得します。

        """
        return list(set(self.required_columns) - set(df.columns))

    def __init__(self, df: pandas.DataFrame, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> None:
        self.custom_production_volume_list = custom_production_volume_list if custom_production_volume_list is not None else []

        if self._duplicated_keys(df):
            logger.warning("引数`df`に重複したキー（project_id, task_id）が含まれています。")

        if not self.required_columns_exist(df):
            raise ValueError(f"引数'df'の'columns'に次の列が存在していません。 {self.missing_required_columns(df)} :: 次の列が必須です。{self.required_columns} の列が必要です。")

        self.df = df

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    def to_non_acceptance(self) -> Task:
        """
        受入フェーズの作業時間を0にした新しいインスタンスを生成します。

        `--task_completion_criteria acceptance_reached`を指定したときに利用します。
        この場合、受入フェーズの作業時間を無視して集計する必要があるためです。

        """
        df = self.df.copy()
        df["first_acceptance_worktime_hour"] = 0
        df["acceptance_worktime_hour"] = 0
        return Task(df, custom_production_volume_list=self.custom_production_volume_list)

    @property
    def optional_columns(self) -> list[str]:
        return [
            # 抜取検査または抜取受入によりスキップされたか
            "inspection_is_skipped",
            "acceptance_is_skipped",
            # 差し戻し後の作業時間
            "post_rejection_annotation_worktime_hour",
            "post_rejection_inspection_worktime_hour",
            "post_rejection_acceptance_worktime_hour",
        ]

    @property
    def required_columns(self) -> list[str]:
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
            # 受入フェーズの日時
            "first_acceptance_reached_datetime",
            "first_acceptance_completed_datetime",
            # 作業時間に関する内容
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            # 個数
            "input_data_count",
            "annotation_count",
            *[e.value for e in self.custom_production_volume_list],
            "inspection_comment_count",
            "inspection_comment_count_in_inspection_phase",
            "inspection_comment_count_in_acceptance_phase",
        ]

    @property
    def columns(self) -> list[str]:
        return self.required_columns + self.optional_columns

    @classmethod
    def from_api_content(
        cls,
        tasks: list[dict[str, Any]],
        task_histories: dict[str, list[dict[str, Any]]],
        inspection_comment_count: InspectionCommentCount,
        annotation_count: AnnotationCount,
        project_id: str,
        annofab_service: annofabapi.Resource,
        *,
        input_data_count: Optional[InputDataCount] = None,
        custom_production_volume: Optional[CustomProductionVolume] = None,
    ) -> Task:
        """
        APIから取得した情報と、DataFrameのラッパーからインスタンスを生成します。

        Args:
            tasks: APIから取得したタスク情報
            task_histories: APIから取得したタスク履歴情報
            inspection_comment_count: 検査コメント数を格納したDataFrameのラッパー
            annotation_count: アノテーション数を格納したDataFrameのラッパー
            input_data_count: 入力データ数を格納したDataFrameのラッパー（タスクに作業対象外のフレームが含まれているときなどに有用なオプション）
            annofab_service: TODO `AddingAdditionalInfoToTask`を修正したら、この引数を削除する。このクラスからAPIに直接アクセスさせたくない。
            custom_production_volume: ユーザー独自の生産量を格納したDataFrameのラッパー
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

        if input_data_count is not None:
            df = df.merge(input_data_count.df, on=["project_id", "task_id"], how="left", suffixes=("_tmp", None))
        df = df.merge(annotation_count.df, on=["project_id", "task_id"], how="left")
        df = df.merge(inspection_comment_count.df, on=["project_id", "task_id"], how="left")
        df = df.fillna(
            {
                "inspection_comment_count": 0,
                "inspection_comment_count_in_inspection_phase": 0,
                "inspection_comment_count_in_acceptance_phase": 0,
                "annotation_count": 0,
                "input_data_count": 1,  # 必ず入力データは1個以上あるので0でなく1にする
            }
        )

        # ユーザー独自の生産量を追加する
        custom_production_volume_list = None
        if custom_production_volume is not None:
            df = df.merge(custom_production_volume.df, on=["project_id", "task_id"], how="left")
            custom_production_volume_list = custom_production_volume.custom_production_volume_list
            df = df.fillna({e.value: 0 for e in custom_production_volume_list})

        return cls(df, custom_production_volume_list=custom_production_volume_list)

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0

    @classmethod
    def empty(cls, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> Task:
        """空のデータフレームを持つインスタンスを生成します。"""

        bool_columns = [
            "inspection_is_skipped",
            "acceptance_is_skipped",
        ]

        string_columns = [
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
            "first_acceptance_reached_datetime",
            "first_acceptance_completed_datetime",
        ]

        numeric_columns = [
            "number_of_rejections_by_inspection",
            "number_of_rejections_by_acceptance",
            "first_annotation_worktime_hour",
            "first_inspection_worktime_hour",
            "first_acceptance_worktime_hour",
            "worktime_hour",
            "annotation_worktime_hour",
            "inspection_worktime_hour",
            "acceptance_worktime_hour",
            "input_data_count",
            "annotation_count",
            "inspection_comment_count",
            "inspection_comment_count_in_inspection_phase",
            "inspection_comment_count_in_acceptance_phase",
        ]
        if custom_production_volume_list is not None:
            numeric_columns.extend([e.value for e in custom_production_volume_list])

        df_dtype: dict[str, str] = {}
        for col in numeric_columns:
            df_dtype[col] = "float"
        for col in string_columns:
            df_dtype[col] = "string"
        for col in bool_columns:
            df_dtype[col] = "boolean"

        columns = string_columns + numeric_columns + bool_columns
        df = pandas.DataFrame(columns=columns).astype(df_dtype)
        return cls(df, custom_production_volume_list=custom_production_volume_list)

    @classmethod
    def from_csv(cls, csv_file: Path, *, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> Task:
        df = pandas.read_csv(str(csv_file))
        return cls(df, custom_production_volume_list=custom_production_volume_list)

    @staticmethod
    def merge(*obj: Task, custom_production_volume_list: Optional[list[ProductionVolumeColumn]] = None) -> Task:
        """
        複数のインスタンスをマージします。

        Notes:
            pandas.DataFrameのインスタンス生成のコストを減らすため、複数の引数を受け取れるようにした。
        """
        df_list = [task.df for task in obj]
        df_merged = pandas.concat(df_list)
        return Task(df_merged, custom_production_volume_list=custom_production_volume_list)

    def plot_histogram_of_worktime(self, output_file: Path, *, metadata: Optional[dict[str, Any]] = None) -> None:
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
            fig = create_histogram_figure(hist, bin_edges, x_axis_label="作業時間[時間]", y_axis_label="タスク数", title=title, sub_title=sub_title)
            figure_list.append(fig)

        # 自動検査したタスクを除外して、検査時間をグラフ化する
        df_ignore_inspection_skipped = df.query("inspection_worktime_hour.notnull() and not inspection_is_skipped")
        sub_title = get_sub_title_from_series(df_ignore_inspection_skipped["inspection_worktime_hour"], decimals=decimals)

        hist, bin_edges = numpy.histogram(df_ignore_inspection_skipped["inspection_worktime_hour"], bins=BIN_COUNT)
        figure_list.append(
            create_histogram_figure(
                hist,
                bin_edges,
                x_axis_label="作業時間[時間]",
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
                x_axis_label="作業時間[時間]",
                y_axis_label="タスク数",
                title="受入作業時間(自動受入されたタスクを除外)",
                sub_title=sub_title,
            )
        )

        nested_figure_list = convert_1d_figure_list_to_2d(figure_list, ncols=3)
        if metadata is not None:
            nested_figure_list.insert(0, [create_pretext_from_metadata(metadata)])

        bokeh_obj = bokeh.layouts.gridplot(nested_figure_list)
        output_file.parent.mkdir(exist_ok=True, parents=True)
        bokeh.plotting.reset_output()
        bokeh.plotting.output_file(output_file, title=output_file.stem)
        bokeh.plotting.save(bokeh_obj)
        logger.debug(f"'{output_file}'を出力しました。")

    def plot_histogram_of_others(self, output_file: Path, *, metadata: Optional[dict[str, Any]] = None) -> None:
        """アノテーション数や、検査コメント数など、作業時間以外の情報をヒストグラムで表示する。

        Args:
            output_file (Path): [description]
        """

        def diff_days(s1: pandas.Series, s2: pandas.Series) -> pandas.Series:
            dt1 = pandas.to_datetime(s1, format="ISO8601")
            dt2 = pandas.to_datetime(s2, format="ISO8601")

            # タイムゾーンを指定している理由::
            # すべてがNaNのseriesをdatetimeに変換すると、型にタイムゾーンが指定されない。
            # その状態で加算すると、`TypeError: DatetimeArray subtraction must have the same timezones or no timezones`というエラーが発生するため
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

        histogram_list_per_category = {
            "production_volume": [
                {"column": "annotation_count", "x_axis_label": "アノテーション数", "title": "アノテーション数"},
                {"column": "input_data_count", "x_axis_label": "入力データ数", "title": "入力データ数"},
                *[{"column": e.value, "x_axis_label": e.name, "title": e.name} for e in self.custom_production_volume_list],
            ],
            "inspection_comment": [
                {"column": "inspection_comment_count", "x_axis_label": "検査コメント数", "title": "検査コメント数"},
                {
                    "column": "inspection_comment_count_in_inspection_phase",
                    "x_axis_label": "検査コメント数",
                    "title": "検査フェーズで付与された検査コメント数",
                },
                {
                    "column": "inspection_comment_count_in_acceptance_phase",
                    "x_axis_label": "検査コメント数",
                    "title": "受入フェーズで付与された検査コメント数",
                },
            ],
            "number_of_rejections": [
                {
                    "column": "number_of_rejections_by_inspection",
                    "x_axis_label": "差し戻し回数",
                    "title": "検査フェーズでの差し戻し回数",
                },
                {
                    "column": "number_of_rejections_by_acceptance",
                    "x_axis_label": "差し戻し回数",
                    "title": "受入フェーズでの差し戻し回数",
                },
            ],
            "days": [
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
            ],
        }

        figure_list_per_category: dict[str, list[figure]] = {}

        for category, histogram_list in histogram_list_per_category.items():
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
            figure_list_per_category[category] = figure_list

        nested_figure_list = []
        for figure_list in figure_list_per_category.values():
            sub_nested_figure_list = convert_1d_figure_list_to_2d(figure_list)
            nested_figure_list.extend(sub_nested_figure_list)

        if metadata is not None:
            nested_figure_list.insert(0, [create_pretext_from_metadata(metadata)])

        bokeh_obj = bokeh.layouts.gridplot(nested_figure_list)
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

        existing_optional_columns = [col for col in self.optional_columns if col in set(self.df.columns)]
        columns = self.required_columns + existing_optional_columns
        print_csv(self.df[columns], str(output_file))

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
        return Task(df, custom_production_volume_list=self.custom_production_volume_list)
