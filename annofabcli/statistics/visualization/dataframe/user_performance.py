# pylint: disable=too-many-lines
"""
各ユーザの合計の生産性と品質
"""
from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Optional

import bokeh
import bokeh.layouts
import bokeh.palettes
import numpy
import pandas
from annofabapi.models import TaskPhase
from bokeh.models.annotations import Span
from bokeh.models.widgets.markups import Div
from bokeh.plotting import ColumnDataSource, figure

from annofabcli.common.utils import print_csv, read_multiheader_csv
from annofabcli.statistics.scatter import (
    create_hover_tool,
    get_color_from_palette,
    plot_bubble,
    plot_scatter,
    write_bokeh_graph,
)
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate

logger = logging.getLogger(__name__)


class WorktimeType(Enum):
    """
    作業時間の種類
    """

    ACTUAL = "actual"
    MONITORED = "monitored"

    @property
    def worktime_type_name(self):
        if self.value == "actual":
            worktime_name = "実績時間"
        elif self.value == "monitored":
            worktime_name = "計測時間"
        else:
            raise RuntimeError(f"'{self.name}'は未対応です。")
        return worktime_name


class PerformanceUnit(Enum):
    """
    生産性の単位
    """

    ANNOTATION_COUNT = "annotation_count"
    INPUT_DATA_COUNT = "input_data_count"

    @property
    def performance_unit_name(self):
        if self.value == "annotation_count":
            performance_unit_name = "アノテーション"
        elif self.value == "input_data_count":
            performance_unit_name = "入力データ"
        else:
            raise RuntimeError(f"'{self.name}'は未対応です。")
        return performance_unit_name


class UserPerformance:
    """
    各ユーザの合計の生産性と品質。
    以下の情報が含まれています。
        * ユーザー情報
        * ユーザーの作業時間（実績作業時間、計測作業時間）
        * ユーザーの作業量（タスク数、入力データ数、アノテーション数）
        * ユーザーが指摘されたコメント数や差し戻された回数
        * 単位量あたりの作業時間
        * 品質の指標（アノテーションあたり指摘されたコメント数、タスクあたり差し戻された回数）
        * 単位量あたりの作業時間の標準偏差

    """

    PLOT_WIDTH = 1200
    PLOT_HEIGHT = 800

    def __init__(self, df: pandas.DataFrame) -> None:
        self.phase_list = self.get_phase_list(df.columns)
        self.df = df

    def is_empty(self) -> bool:
        """
        空のデータフレームを持つかどうかを返します。

        Returns:
            空のデータフレームを持つかどうか
        """
        return len(self.df) == 0

    @staticmethod
    def _add_ratio_column_for_productivity_per_user(df: pandas.DataFrame, phase_list: list[str]) -> None:
        """
        ユーザーの生産性に関する列を、DataFrameに追加します。
        """

        # 集計対象タスクから算出した計測作業時間（`monitored_worktime_hour`）に対応する実績作業時間を推定で算出する
        # 具体的には、実際の計測作業時間と十先作業時間の比（`real_monitored_worktime_hour/real_actual_worktime_hour`）になるように按分する
        df[("actual_worktime_hour", "sum")] = (
            df[("monitored_worktime_hour", "sum")] / df[("real_monitored_worktime_hour/real_actual_worktime_hour", "sum")]
        )

        for phase in phase_list:

            def get_monitored_worktime_ratio(row: pandas.Series) -> float:
                """

                計測作業時間の合計値が0により、monitored_worktime_ratioはnanになる場合は、教師付の実績作業時間を実績作業時間の合計値になるようなmonitored_worktime_ratioに変更する
                """
                if row[("monitored_worktime_hour", "sum")] == 0:
                    if phase == TaskPhase.ANNOTATION.value:  # noqa: B023
                        return 1
                    else:
                        return 0
                else:
                    return (
                        row[("monitored_worktime_hour", phase)]  # noqa: B023
                        / row[("monitored_worktime_hour", "sum")]
                    )

            # Annofab時間の比率
            df[("monitored_worktime_ratio", phase)] = df.apply(get_monitored_worktime_ratio, axis=1)

            # Annofab時間の比率から、Annowork時間を予測する
            df[("actual_worktime_hour", phase)] = df[("actual_worktime_hour", "sum")] * df[("monitored_worktime_ratio", phase)]

            # 生産性を算出
            df[("monitored_worktime_hour/input_data_count", phase)] = df[("monitored_worktime_hour", phase)] / df[("input_data_count", phase)]
            df[("actual_worktime_hour/input_data_count", phase)] = df[("actual_worktime_hour", phase)] / df[("input_data_count", phase)]

            df[("monitored_worktime_hour/annotation_count", phase)] = df[("monitored_worktime_hour", phase)] / df[("annotation_count", phase)]
            df[("actual_worktime_hour/annotation_count", phase)] = df[("actual_worktime_hour", phase)] / df[("annotation_count", phase)]

            ratio__actual_vs_monitored_worktime = df[("actual_worktime_hour", phase)] / df[("monitored_worktime_hour", phase)]
            df[("stdev__actual_worktime_hour/input_data_count", phase)] = (
                df[("stdev__monitored_worktime_hour/input_data_count", phase)] * ratio__actual_vs_monitored_worktime
            )
            df[("stdev__actual_worktime_hour/annotation_count", phase)] = (
                df[("stdev__monitored_worktime_hour/annotation_count", phase)] * ratio__actual_vs_monitored_worktime
            )

        phase = TaskPhase.ANNOTATION.value
        df[("pointed_out_inspection_comment_count/annotation_count", phase)] = (
            df[("pointed_out_inspection_comment_count", phase)] / df[("annotation_count", phase)]
        )
        df[("pointed_out_inspection_comment_count/input_data_count", phase)] = (
            df[("pointed_out_inspection_comment_count", phase)] / df[("input_data_count", phase)]
        )
        df[("rejected_count/task_count", phase)] = df[("rejected_count", phase)] / df[("task_count", phase)]

    @staticmethod
    def get_phase_list(columns: list[tuple[str, str]]) -> list[str]:
        """
        サポートしているフェーズのlistを取得します。
        `monitored_worktime_hour`列情報を見て、サポートしているフェーズを判断します。

        """
        tmp_set = {c1 for c0, c1 in columns if c0 == "monitored_worktime_hour"}
        phase_list = []

        for phase in TaskPhase:
            if phase.value in tmp_set:
                phase_list.append(phase.value)  # noqa: PERF401

        return phase_list

    @classmethod
    def from_csv(cls, csv_file: Path) -> UserPerformance:
        df = read_multiheader_csv(str(csv_file))
        return cls(df)

    @classmethod
    def empty(cls) -> UserPerformance:
        """空のデータフレームを持つインスタンスを生成します。"""

        df_dtype: dict[tuple[str, str], str] = {
            ("account_id", ""): "string",
            ("user_id", ""): "string",
            ("username", ""): "string",
            ("biography", ""): "string",
            ("last_working_date", ""): "string",
            ("real_monitored_worktime_hour", "sum"): "float64",
            ("real_monitored_worktime_hour", "annotation"): "float64",
            ("real_monitored_worktime_hour", "inspection"): "float64",
            ("real_monitored_worktime_hour", "acceptance"): "float64",
            # phaseがinspection, acceptanceの列は出力されない可能性があるので、絶対出力される"sum", "annotation"の列のみ定義する
            ("monitored_worktime_hour", "annotation"): "float64",
            ("monitored_worktime_hour", "sum"): "float64",
            ("task_count", "annotation"): "float64",
            ("input_data_count", "annotation"): "float64",
            ("annotation_count", "annotation"): "float64",
            ("real_actual_worktime_hour", "sum"): "float64",
            ("real_monitored_worktime_hour/real_actual_worktime_hour", "sum"): "float64",
            ("actual_worktime_hour", "sum"): "float64",
            ("actual_worktime_hour", "annotation"): "float64",
            ("pointed_out_inspection_comment_count", "annotation"): "float64",
            ("rejected_count", "annotation"): "float64",
        }

        df = pandas.DataFrame(columns=pandas.MultiIndex.from_tuples(df_dtype.keys())).astype(df_dtype)
        return cls(df)

    def actual_worktime_exists(self) -> bool:
        """実績作業時間が入力されているか否か"""
        return self.df[("actual_worktime_hour", "sum")].sum() > 0

    @staticmethod
    def create_df_stdev_worktime(df_worktime_ratio: pandas.DataFrame) -> pandas.DataFrame:
        """
        単位量あたり作業時間の標準偏差のDataFrameを生成する
        """
        df_worktime_ratio2 = df_worktime_ratio.copy()
        df_worktime_ratio2["worktime_hour/input_data_count"] = df_worktime_ratio2["worktime_hour"] / df_worktime_ratio2["input_data_count"]
        df_worktime_ratio2["worktime_hour/annotation_count"] = df_worktime_ratio2["worktime_hour"] / df_worktime_ratio2["annotation_count"]

        # 母標準偏差を算出する
        df_stdev = df_worktime_ratio2.groupby(["account_id", "phase"])[["worktime_hour/input_data_count", "worktime_hour/annotation_count"]].std(
            ddof=0
        )

        df_stdev2 = pandas.pivot_table(
            df_stdev,
            values=["worktime_hour/input_data_count", "worktime_hour/annotation_count"],
            index="account_id",
            columns="phase",
        )
        df_stdev3 = df_stdev2.rename(
            columns={
                "worktime_hour/input_data_count": "stdev__monitored_worktime_hour/input_data_count",
                "worktime_hour/annotation_count": "stdev__monitored_worktime_hour/annotation_count",
            }
        )

        return df_stdev3

    @staticmethod
    def _create_df_monitored_worktime_and_production_amount(
        task_worktime_by_phase_user: TaskWorktimeByPhaseUser,
    ) -> pandas.DataFrame:
        """
        タスク情報から算出した計測作業時間や生産量、指摘数などの情報が格納されたDataFrameを生成します。

        Returns: 生成されるDataFrame
            columns(level0):
                * monitored_worktime_hour
                * task_count
                * input_data_count
                * annotation_count
                * pointed_out_inspection_comment_count
                * rejected_count
            columns(level1): ${phase}
            index: account_id
        """
        df = task_worktime_by_phase_user.df
        if len(df) == 0:
            # 集計対象のタスクが0件の場合など
            # 生産量、指摘の量の情報は、生産性や品質の列を算出するのに必要なので、columnsに追加する
            phase = TaskPhase.ANNOTATION.value
            columns = pandas.MultiIndex.from_tuples(
                [
                    ("monitored_worktime_hour", "sum"),
                    ("monitored_worktime_hour", phase),
                    ("task_count", phase),
                    ("input_data_count", phase),
                    ("annotation_count", phase),
                    ("pointed_out_inspection_comment_count", phase),
                    ("rejected_count", phase),
                ]
            )

            df_empty = pandas.DataFrame(columns=columns, index=pandas.Index([], name="account_id"), dtype="float64")
            return df_empty

        # TODO もしかしたら  `["worktime_hour"]>0]`を指定する必要があるかもしれない。分からないので、いったん指定しない
        df2 = df.pivot_table(
            values=[
                "worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
                "pointed_out_inspection_comment_count",
                "rejected_count",
            ],
            columns="phase",
            index="account_id",
            aggfunc="sum",
        ).fillna(0)
        df2 = df2.rename(columns={"worktime_hour": "monitored_worktime_hour"})

        phase_list = list(df2["monitored_worktime_hour"].columns)

        # 計測作業時間の合計値を算出する
        df2[("monitored_worktime_hour", "sum")] = df2[[("monitored_worktime_hour", phase) for phase in phase_list]].sum(axis=1)

        return df2

    @staticmethod
    def _create_df_stdev_monitored_worktime(task_worktime_by_phase_user: TaskWorktimeByPhaseUser) -> pandas.DataFrame:
        """
        単位量あたり計測作業時間の標準偏差が格納されたDataFrameを生成します。

        Returns:
            以下の情報を持つDataFrame
                index: account_id
                column0:
                    * stdev__monitored_worktime_hour/input_data_count
                    * stdev__monitored_worktime_hour/annotation_count
                column1: ${phase}

        """
        df = task_worktime_by_phase_user.df
        if len(df) == 0:
            # 集計対象のタスクが0件のとき
            # `to_csv()`で出力したときにKeyErrorが発生内容にするため、事前に列を追加しておく
            phase = TaskPhase.ANNOTATION.value
            columns = pandas.MultiIndex.from_tuples(
                [
                    ("stdev__monitored_worktime_hour/input_data_count", phase),
                    ("stdev__monitored_worktime_hour/annotation_count", phase),
                ]
            )
            df_empty = pandas.DataFrame(columns=columns, index=pandas.Index([], name="account_id"), dtype="float64")
            return df_empty

        df2 = df.copy()
        df2["worktime_hour/input_data_count"] = df2["worktime_hour"] / df2["input_data_count"]
        df2["worktime_hour/annotation_count"] = df2["worktime_hour"] / df2["annotation_count"]

        # 母標準偏差(ddof=0)を算出する
        # 標準偏差を算出する際"inf"を除外する理由：annotation_countが0の場合、"worktime_hour/annotation_count"はinfになる。
        # infが含まれるデータから標準偏差を求めようとするNaNになる。したがって、infを除外する。
        # 原則annotation_countが0のときに場合は、作業時間も小さいためこのデータを除外しても、標準偏差には影響がないはず
        df_stdev_per_input_data_count = (
            df2[df2["worktime_hour/input_data_count"] != float("inf")]
            .groupby(["account_id", "phase"])[["worktime_hour/input_data_count"]]
            .std(ddof=0)
        )
        df_stdev_per_annotation_count = (
            df2[df2["worktime_hour/annotation_count"] != float("inf")]
            .groupby(["account_id", "phase"])[["worktime_hour/annotation_count"]]
            .std(ddof=0)
        )
        df_stdev = pandas.concat([df_stdev_per_input_data_count, df_stdev_per_annotation_count], axis=1)

        # `dropna=False`を指定する理由：NaNが含まれることにより、列に"annotation"などが含まれないと、後続の処理で失敗するため
        # 前述の処理でinfを除外しているので、NaNが含まれることはないはず
        df_stdev2 = pandas.pivot_table(
            df_stdev, values=["worktime_hour/input_data_count", "worktime_hour/annotation_count"], index="account_id", columns="phase", dropna=False
        )
        df_stdev3 = df_stdev2.rename(
            columns={
                "worktime_hour/input_data_count": "stdev__monitored_worktime_hour/input_data_count",
                "worktime_hour/annotation_count": "stdev__monitored_worktime_hour/annotation_count",
            }
        )

        return df_stdev3

    @staticmethod
    def _create_df_real_worktime(worktime_per_date: WorktimePerDate) -> pandas.DataFrame:
        """
        集計対象タスクに影響されない実際の計測作業時間と実績作業時間が格納されたDataFrameを生成します。

        Returns:
            以下の情報を持つDataFrame
                index: account_id
                columns:
                    ("real_actual_worktime_hour", "sum")
                    ("real_monitored_worktime_hour", "sum")
                    ("real_monitored_worktime_hour", "annotation")
                    ("real_monitored_worktime_hour", "inspection")
                    ("real_monitored_worktime_hour", "acceptance")
                    ("real_monitored_worktime_hour/real_actual_worktime_hour", "sum")

        """
        df = worktime_per_date.df
        if len(df) > 0:
            df_agg_worktime = df.pivot_table(
                values=[
                    "actual_worktime_hour",
                    "monitored_worktime_hour",
                    "monitored_annotation_worktime_hour",
                    "monitored_inspection_worktime_hour",
                    "monitored_acceptance_worktime_hour",
                ],
                index="account_id",
                aggfunc="sum",
            )
        else:
            # 引数`df`のlengthが0でも、エラーにならないようにDataFrameを生成する
            # https://qiita.com/yuji38kwmt/items/93dd31c840fd55d6ac7a
            df_agg_worktime = pandas.DataFrame(
                columns=[
                    "actual_worktime_hour",
                    "monitored_worktime_hour",
                    "monitored_annotation_worktime_hour",
                    "monitored_inspection_worktime_hour",
                    "monitored_acceptance_worktime_hour",
                ],
                index=pandas.Index([], name="account_id"),
            )

        # 列をMultiIndexに変更する
        df_agg_worktime = df_agg_worktime[
            [
                "actual_worktime_hour",
                "monitored_worktime_hour",
                "monitored_annotation_worktime_hour",
                "monitored_inspection_worktime_hour",
                "monitored_acceptance_worktime_hour",
            ]
        ]
        df_agg_worktime.columns = pandas.MultiIndex.from_tuples(
            [
                ("real_actual_worktime_hour", "sum"),
                ("real_monitored_worktime_hour", "sum"),
                ("real_monitored_worktime_hour", "annotation"),
                ("real_monitored_worktime_hour", "inspection"),
                ("real_monitored_worktime_hour", "acceptance"),
            ]
        )

        df_agg_worktime[("real_monitored_worktime_hour/real_actual_worktime_hour", "sum")] = (
            df_agg_worktime[("real_monitored_worktime_hour", "sum")] / df_agg_worktime[("real_actual_worktime_hour", "sum")]
        )

        return df_agg_worktime

    @staticmethod
    def _create_df_working_period(worktime_per_date: WorktimePerDate) -> pandas.DataFrame:
        """
        作業期間情報を含むDataFrameを生成します。
        作業期間は計測作業時間から算出します。

        Returns:
            以下の情報を持つDataFrame
                index: account_id
                columns:
                    ("first_working_date", "")
                    ("last_working_date", "")
                    ("working_days", "")
        """
        df = worktime_per_date.df
        df1 = df[df["monitored_worktime_hour"] > 0]
        if len(df1) > 0:
            df2 = df1.pivot_table(values="date", index="account_id", aggfunc=["min", "max"])
            df2.columns = pandas.MultiIndex.from_tuples([("first_working_date", ""), ("last_working_date", "")])
        else:
            df2 = pandas.DataFrame(
                columns=pandas.MultiIndex.from_tuples([("first_working_date", ""), ("last_working_date", "")]),
                index=pandas.Index([], name="account_id"),
            )

        # 元のDataFrame`df`が`account_id`,`date`のペアでユニークになっていない可能性も考えて、事前に`account_id`と`date`で集計する
        df3 = df.groupby(["account_id", "date"])[["monitored_worktime_hour"]].sum()
        # 作業日数を算出する
        df3 = df3[df3["monitored_worktime_hour"] > 0].groupby("account_id").count()
        df3.columns = pandas.MultiIndex.from_tuples([("working_days", "")])

        # joinしない理由: レベル1の列名が空文字のDataFrameをjoinすると、Python3.12のpandas2.2.0で、列名が期待通りにならないため
        # https://github.com/pandas-dev/pandas/issues/57500
        # return df2.join(df3)
        return pandas.concat([df2, df3], axis=1)

    @staticmethod
    def _create_df_user(worktime_per_date: WorktimePerDate) -> pandas.DataFrame:
        """
        ユーザー情報が格納されたDataFrameを生成します。ただし列はMultiIndexです。

        Returns:
            column0:
                ("user_id", "")
                ("username", "")
                ("biography", "")
            column1: ""
            index: account_id
        """
        df = worktime_per_date.df
        df2 = df[["account_id", "user_id", "username", "biography"]]
        df2 = df2.drop_duplicates()
        df2 = df2.set_index("account_id")
        df2.columns = pandas.MultiIndex.from_tuples([("user_id", ""), ("username", ""), ("biography", "")])
        return df2

    @classmethod
    def from_df_wrapper(
        cls,
        worktime_per_date: WorktimePerDate,
        task_worktime_by_phase_user: TaskWorktimeByPhaseUser,
    ) -> UserPerformance:
        """
        pandas.DataFrameをラップしたオブジェクトから、インスタンスを生成します。

        Args:
            worktime_per_date: 日ごとの作業時間が記載されたDataFrameを格納したオブジェクト。ユーザー情報の取得や、実際の作業時間（集計タスクに影響しない）の算出に利用します。
            task_worktime_by_phase_user: タスク、フェーズ、ユーザーごとの作業時間や生産量が格納されたオブジェクト。生産量やタスクにかかった作業時間の取得に利用します。


        """  # noqa: E501

        def drop_unnecessary_columns(df: pandas.DataFrame) -> pandas.DataFrame:
            """
            出力しない列を削除したDataFrameを返します。

            Returns:
                以下の列を削除します。
                * level0がpointed_out_inspection_comment_countで、level1がinspection, acceptanceの列
                * level0がrejected_countで、level1がinspection, acceptanceの列
            """
            tmp_phases = set(phase_list) - {TaskPhase.ANNOTATION.value}
            dropped_column = []
            dropped_column.extend([("pointed_out_inspection_comment_count", phase) for phase in tmp_phases])
            dropped_column.extend([("rejected_count", phase) for phase in tmp_phases])
            # 'errors="ignore"を指定する理由：削除する列が存在しないときでも、処理を継続するため
            return df.drop(dropped_column, axis=1, errors="ignore")

        def fillna_for_production_amount(df: pandas.DataFrame) -> pandas.DataFrame:
            """
            生産量や指摘数などの情報が欠損している場合は、0で埋めます。そうしないと、生産性や品質情報を計算する際にエラーになるためです。
            """
            level0_columns = [
                "monitored_worktime_hour",
                "task_count",
                "input_data_count",
                "annotation_count",
                "pointed_out_inspection_comment_count",
                "rejected_count",
            ]
            columns = [(c0, c1) for c0, c1 in df.columns if c0 in level0_columns]

            return df.fillna({col: 0 for col in columns})

        # 実際の計測作業時間情報（集計タスクに影響されない作業時間）と実績作業時間を算出する
        df = cls._create_df_real_worktime(worktime_per_date)

        # 集計対象タスクから計測作業時間や生産量を算出する
        df = df.join(cls._create_df_monitored_worktime_and_production_amount(task_worktime_by_phase_user))
        # 左結合でjoinした結果、生産量や指摘回数がNaNになる可能性があるので、fillnaで0を埋める
        df = fillna_for_production_amount(df)

        phase_list = cls.get_phase_list(list(df.columns))

        # 集計対象タスクから単位量あたり計測作業時間の標準偏差を算出する
        df = df.join(cls._create_df_stdev_monitored_worktime(task_worktime_by_phase_user))

        # 比例関係の列を計算して追加する
        cls._add_ratio_column_for_productivity_per_user(df, phase_list=phase_list)

        # 出力に不要な列を削除する
        df = drop_unnecessary_columns(df)

        # ユーザ情報を結合する
        # joinしない理由: レベル1の列名が空文字のDataFrameをjoinすると、Python3.12のpandas2.2.0で、列名が期待通りにならないため
        # https://github.com/pandas-dev/pandas/issues/57500
        # df = df.join(cls._create_df_user(worktime_per_date))
        df = pandas.concat([df, cls._create_df_user(worktime_per_date)], axis=1)

        # 作業期間に関する情報を算出する
        df = df.join(cls._create_df_working_period(worktime_per_date))

        df = df.sort_values(["user_id"])
        # `df.reset_index()`を実行する理由：indexである`account_id`を列にするため
        return cls(df.reset_index())

    @classmethod
    def _convert_column_dtypes(cls, df: pandas.DataFrame) -> pandas.DataFrame:
        """
        引数`df`の列の型を正しい型に変換する。
        """

        columns = set(df.columns)
        # 列ヘッダに相当する列名
        basic_columns = [
            ("account_id", ""),
            ("user_id", ""),
            ("username", ""),
            ("biography", ""),
            ("first_working_date", ""),
            ("last_working_date", ""),
            ("working_days", ""),
        ]

        value_columns = columns - set(basic_columns)
        dtypes = {col: "string" for col in basic_columns}
        dtypes.update({col: "float64" for col in value_columns})
        return df.astype(dtypes)

    def _validate_df_for_output(self, output_file: Path) -> bool:
        if len(self.df) == 0:
            logger.warning(f"データが0件のため、{output_file} は出力しません。")
            return False
        return True

    @staticmethod
    def get_productivity_columns(phase_list: list[str]) -> list[tuple[str, str]]:
        """
        生産性に関する情報（作業時間、生産量、生産量あたり作業時間）の列を取得します。
        """
        # `phase_list`を参照しない理由： `phase_list`は集計対象のタスクから求めた作業時間を元に決めている
        # `real_monitored_worktime_hour`は実際に作業した時間を表すため、`phase_list`を参照していない。
        # `phase_list`を参照しないことで、以下のケースにも対応できる
        #   * 実際には受入作業しているが、受入作業を実施したタスクが集計対象でない
        real_monitored_worktime_columns = [
            ("real_monitored_worktime_hour", "sum"),
            ("real_monitored_worktime_hour", "annotation"),
            ("real_monitored_worktime_hour", "inspection"),
            ("real_monitored_worktime_hour", "acceptance"),
        ]

        monitored_worktime_columns = (
            [("monitored_worktime_hour", "sum")]
            + [("monitored_worktime_hour", phase) for phase in phase_list]
            + [("monitored_worktime_ratio", phase) for phase in phase_list]
        )
        production_columns = (
            [("task_count", phase) for phase in phase_list]
            + [("input_data_count", phase) for phase in phase_list]
            + [("annotation_count", phase) for phase in phase_list]
        )

        real_actual_worktime_columns = [
            ("real_actual_worktime_hour", "sum"),
            ("real_monitored_worktime_hour/real_actual_worktime_hour", "sum"),
        ]
        actual_worktime_columns = [("actual_worktime_hour", "sum")] + [("actual_worktime_hour", phase) for phase in phase_list]

        productivity_columns = (
            [("monitored_worktime_hour/input_data_count", phase) for phase in phase_list]
            + [("actual_worktime_hour/input_data_count", phase) for phase in phase_list]
            + [("monitored_worktime_hour/annotation_count", phase) for phase in phase_list]
            + [("actual_worktime_hour/annotation_count", phase) for phase in phase_list]
        )

        inspection_comment_columns = [
            ("pointed_out_inspection_comment_count", TaskPhase.ANNOTATION.value),
            ("pointed_out_inspection_comment_count/input_data_count", TaskPhase.ANNOTATION.value),
            ("pointed_out_inspection_comment_count/annotation_count", TaskPhase.ANNOTATION.value),
        ]

        rejected_count_columns = [
            ("rejected_count", TaskPhase.ANNOTATION.value),
            ("rejected_count/task_count", TaskPhase.ANNOTATION.value),
        ]

        stdev_columns = (
            [("stdev__monitored_worktime_hour/input_data_count", phase) for phase in phase_list]
            + [("stdev__actual_worktime_hour/input_data_count", phase) for phase in phase_list]
            + [("stdev__monitored_worktime_hour/annotation_count", phase) for phase in phase_list]
            + [("stdev__actual_worktime_hour/annotation_count", phase) for phase in phase_list]
        )

        prior_columns = (
            real_monitored_worktime_columns
            + monitored_worktime_columns
            + production_columns
            + real_actual_worktime_columns
            + actual_worktime_columns
            + productivity_columns
            + inspection_comment_columns
            + rejected_count_columns
            + stdev_columns
        )

        return prior_columns

    def to_csv(self, output_file: Path) -> None:
        if not self._validate_df_for_output(output_file):
            return

        value_columns = self.get_productivity_columns(self.phase_list)

        user_columns = [
            ("account_id", ""),
            ("user_id", ""),
            ("username", ""),
            ("biography", ""),
            ("first_working_date", ""),
            ("last_working_date", ""),
            ("working_days", ""),
        ]
        columns = user_columns + value_columns
        print_csv(self.df[columns], str(output_file))

    @staticmethod
    def _plot_average_line(fig: figure, value: float, dimension: str) -> None:
        span_average_line = Span(
            location=value,
            dimension=dimension,
            line_color="red",
            line_width=0.5,
        )
        fig.add_layout(span_average_line)

    @staticmethod
    def _plot_quartile_line(fig: figure, quartile: tuple[float, float, float], dimension: str) -> None:
        """

        Args:
            fig (bokeh.plotting.Figure):
            quartile (tuple[float, float, float]): 四分位数。tuple[25%値, 50%値, 75%値]
            dimension (str): [description]: width or height
        """

        for value in quartile:
            span_average_line = Span(
                location=value,
                dimension=dimension,
                line_color="blue",
                line_width=0.5,
            )
            fig.add_layout(span_average_line)

    @staticmethod
    def _get_average_value(df: pandas.DataFrame, numerator_column: tuple[str, str], denominator_column: tuple[str, str]) -> Optional[float]:
        numerator = df[numerator_column].sum()
        denominator = df[denominator_column].sum()
        if denominator > 0:
            return numerator / denominator
        else:
            return None

    @staticmethod
    def _get_quartile_value(df: pandas.DataFrame, column: tuple[str, str]) -> Optional[tuple[float, float, float]]:
        tmp = df[column].describe()
        if tmp["count"] > 3:
            return (tmp["25%"], tmp["50%"], tmp["75%"])
        else:
            return None

    @staticmethod
    def _create_div_element() -> Div:
        """
        HTMLページの先頭に付与するdiv要素を生成する。
        """
        return Div(
            text="""<h4>グラフの見方</h4>
            <span style="color:red;">赤線</span>：平均値<br>
            <span style="color:blue;">青線</span>：四分位数<br>
            """
        )

    @staticmethod
    def _set_legend(fig: figure) -> None:
        """
        凡例の設定。
        """
        fig.legend.location = "top_left"
        fig.legend.click_policy = "mute"
        fig.legend.title = "biography"
        if len(fig.legend) > 0:
            legend = fig.legend[0]
            fig.add_layout(legend, "left")

    @staticmethod
    def _add_ratio_key_for_whole_productivity(series: pandas.Series, phase_list: list[str]) -> None:
        """
        プロジェクト全体の生産性に関するkeyを、pandas.Seriesに追加します。
        """
        # ゼロ割の警告を無視する
        with numpy.errstate(divide="ignore", invalid="ignore"):
            series[("real_monitored_worktime_hour/real_actual_worktime_hour", "sum")] = (
                series[("real_monitored_worktime_hour", "sum")] / series[("real_actual_worktime_hour", "sum")]
            )

            for phase in phase_list:
                # Annofab時間の比率を算出
                # 計測作業時間の合計値が0により、monitored_worktime_ratioはnanになる場合は、教師付の実績作業時間を実績作業時間の合計値になるようなmonitored_worktime_ratioに変更する  # noqa: E501
                if series[("monitored_worktime_hour", "sum")] == 0:
                    if phase == TaskPhase.ANNOTATION.value:
                        series[("monitored_worktime_ratio", phase)] = 1
                    else:
                        series[("monitored_worktime_ratio", phase)] = 0
                else:
                    series[("monitored_worktime_ratio", phase)] = (
                        series[("monitored_worktime_hour", phase)] / series[("monitored_worktime_hour", "sum")]
                    )

                # Annofab時間の比率から、Annowork時間を予測する
                series[("actual_worktime_hour", phase)] = series[("actual_worktime_hour", "sum")] * series[("monitored_worktime_ratio", phase)]

                # 生産性を算出
                series[("monitored_worktime_hour/input_data_count", phase)] = (
                    series[("monitored_worktime_hour", phase)] / series[("input_data_count", phase)]
                )
                series[("actual_worktime_hour/input_data_count", phase)] = (
                    series[("actual_worktime_hour", phase)] / series[("input_data_count", phase)]
                )

                series[("monitored_worktime_hour/annotation_count", phase)] = (
                    series[("monitored_worktime_hour", phase)] / series[("annotation_count", phase)]
                )
                series[("actual_worktime_hour/annotation_count", phase)] = (
                    series[("actual_worktime_hour", phase)] / series[("annotation_count", phase)]
                )

            phase = TaskPhase.ANNOTATION.value
            series[("pointed_out_inspection_comment_count/annotation_count", phase)] = (
                series[("pointed_out_inspection_comment_count", phase)] / series[("annotation_count", phase)]
            )
            series[("pointed_out_inspection_comment_count/input_data_count", phase)] = (
                series[("pointed_out_inspection_comment_count", phase)] / series[("input_data_count", phase)]
            )
            series[("rejected_count/task_count", phase)] = series[("rejected_count", phase)] / series[("task_count", phase)]

    def plot_productivity(self, output_file: Path, worktime_type: WorktimeType, performance_unit: PerformanceUnit) -> None:
        """作業時間と生産性の関係をメンバごとにプロットする。"""

        if not self._validate_df_for_output(output_file):
            return

        # numpy.inf が含まれていると散布図を出力できないので置換する
        df = self.df.replace(numpy.inf, numpy.nan)

        performance_unit_name = performance_unit.performance_unit_name

        def create_figure(title: str) -> figure:
            return figure(
                width=self.PLOT_WIDTH,
                height=self.PLOT_HEIGHT,
                title=title,
                x_axis_label="累計作業時間[hour]",
                y_axis_label=f"{performance_unit_name}あたり作業時間[minute/annotation]",
            )

        logger.debug(f"{output_file} を出力します。")

        DICT_PHASE_NAME = {
            TaskPhase.ANNOTATION.value: "教師付",
            TaskPhase.INSPECTION.value: "検査",
            TaskPhase.ACCEPTANCE.value: "受入",
        }
        figure_list = [
            create_figure(f"{DICT_PHASE_NAME[phase]}の{performance_unit_name}あたり作業時間と累計作業時間の関係({worktime_type.worktime_type_name})")
            for phase in self.phase_list
        ]

        df["biography"] = df["biography"].fillna("")

        x_column = f"{worktime_type.value}_worktime_hour"
        y_column = f"{worktime_type.value}_worktime_minute/{performance_unit.value}"
        # 分単位の生産性を算出する
        for phase in self.phase_list:
            df[(f"{worktime_type.value}_worktime_minute/{performance_unit.value}", phase)] = (
                df[(f"{worktime_type.value}_worktime_hour/{performance_unit.value}", phase)] * 60
            )

        # bokeh3.0.3では、string型の列を持つpandas.DataFrameを描画できないため、改めてobject型に戻す
        # TODO この問題が解決されたら、削除する
        # https://qiita.com/yuji38kwmt/items/b5da6ed521e827620186
        df = df.astype(
            {
                ("account_id", ""): "object",
                ("user_id", ""): "object",
                ("username", ""): "object",
                ("biography", ""): "object",
                ("first_working_date", ""): "object",
                ("last_working_date", ""): "object",
            }
        )

        for biography_index, biography in enumerate(sorted(set(df["biography"]))):
            for fig, phase in zip(figure_list, self.phase_list):
                filtered_df = df[(df["biography"] == biography) & df[(x_column, phase)].notna() & df[(y_column, phase)].notna()]
                if len(filtered_df) == 0:
                    continue
                source = ColumnDataSource(data=filtered_df)
                plot_scatter(
                    fig=fig,
                    source=source,
                    x_column_name=f"{x_column}_{phase}",
                    y_column_name=f"{y_column}_{phase}",
                    text_column_name="username_",
                    legend_label=biography,
                    color=get_color_from_palette(biography_index),
                )

        for fig, phase in zip(figure_list, self.phase_list):
            average_hour = self._get_average_value(
                df,
                numerator_column=(f"{worktime_type.value}_worktime_hour", phase),
                denominator_column=(performance_unit.value, phase),
            )
            if average_hour is not None:
                average_minute = average_hour * 60
                self._plot_average_line(fig, average_minute, dimension="width")

            quartile = self._get_quartile_value(df, (f"{worktime_type.value}_worktime_minute/{performance_unit.value}", phase))
            if quartile is not None:
                self._plot_quartile_line(fig, quartile, dimension="width")

        for fig, phase in zip(figure_list, self.phase_list):
            tooltip_item = [
                "user_id_",
                "username_",
                "biography_",
                f"{worktime_type.value}_worktime_hour_{phase}",
                f"task_count_{phase}",
                f"input_data_count_{phase}",
                f"annotation_count_{phase}",
                f"{worktime_type.value}_worktime_hour/input_data_count_{phase}",
                f"{worktime_type.value}_worktime_hour/annotation_count_{phase}",
                "first_working_date_",
                "last_working_date_",
                "working_days_",
            ]

            hover_tool = create_hover_tool(tooltip_item)
            fig.add_tools(hover_tool)
            self._set_legend(fig)

        div_element = self._create_div_element()
        write_bokeh_graph(bokeh.layouts.column([div_element, *figure_list]), output_file)

    def plot_quality(self, output_file: Path) -> None:
        """
        メンバごとに品質を散布図でプロットする

        Args:
            df:
        Returns:

        """
        if not self._validate_df_for_output(output_file):
            return

        # numpy.inf が含まれていると散布図を出力できないので置換する
        df = self.df.replace(numpy.inf, numpy.nan)

        def create_figure(title: str, x_axis_label: str, y_axis_label: str) -> figure:
            return figure(
                width=self.PLOT_WIDTH,
                height=self.PLOT_HEIGHT,
                title=title,
                x_axis_label=x_axis_label,
                y_axis_label=y_axis_label,
            )

        logger.debug(f"{output_file} を出力します。")

        figure_list = [
            create_figure(title="タスクあたり差し戻し回数とタスク数の関係", x_axis_label="タスク数", y_axis_label="タスクあたり差し戻し回数"),
            create_figure(
                title="アノテーションあたり検査コメント数とアノテーション数の関係",
                x_axis_label="アノテーション数",
                y_axis_label="アノテーションあたり検査コメント数",
            ),
        ]
        column_pair_list = [
            ("task_count", "rejected_count/task_count"),
            ("annotation_count", "pointed_out_inspection_comment_count/annotation_count"),
        ]

        phase = "annotation"

        # bokeh3.0.3では、string型の列を持つpandas.DataFrameを描画できないため、改めてobject型に戻す
        # TODO この問題が解決されたら、削除する
        # https://qiita.com/yuji38kwmt/items/b5da6ed521e827620186
        df = df.astype(
            {
                ("account_id", ""): "object",
                ("user_id", ""): "object",
                ("username", ""): "object",
                ("biography", ""): "object",
                ("first_working_date", ""): "object",
                ("last_working_date", ""): "object",
            }
        )

        df["biography"] = df["biography"].fillna("")
        for biography_index, biography in enumerate(sorted(set(df["biography"]))):
            for column_pair, fig in zip(column_pair_list, figure_list):
                x_column = column_pair[0]
                y_column = column_pair[1]
                filtered_df = df[(df["biography"] == biography) & df[(x_column, phase)].notna() & df[(y_column, phase)].notna()]
                if len(filtered_df) == 0:
                    continue

                source = ColumnDataSource(data=filtered_df)
                plot_scatter(
                    fig=fig,
                    source=source,
                    x_column_name=f"{x_column}_{phase}",
                    y_column_name=f"{y_column}_{phase}",
                    text_column_name="username_",
                    legend_label=biography,
                    color=get_color_from_palette(biography_index),
                )

        for column_pair, fig in zip(
            [("rejected_count", "task_count"), ("pointed_out_inspection_comment_count", "annotation_count")],
            figure_list,
        ):
            average_value = self._get_average_value(df, numerator_column=(column_pair[0], phase), denominator_column=(column_pair[1], phase))
            if average_value is not None:
                self._plot_average_line(fig, average_value, dimension="width")

        for column, fig in zip(
            ["rejected_count/task_count", "pointed_out_inspection_comment_count/annotation_count"],
            figure_list,
        ):
            quartile = self._get_quartile_value(df, (column, phase))
            if quartile is not None:
                self._plot_quartile_line(fig, quartile, dimension="width")

        for fig in figure_list:
            tooltip_item = [
                "user_id_",
                "username_",
                "biography_",
                f"monitored_worktime_hour_{phase}",
                f"task_count_{phase}",
                f"input_data_count_{phase}",
                f"annotation_count_{phase}",
                f"rejected_count_{phase}",
                f"pointed_out_inspection_comment_count_{phase}",
                f"rejected_count/task_count_{phase}",
                f"pointed_out_inspection_comment_count/annotation_count_{phase}",
                "first_working_date_",
                "last_working_date_",
                "working_days_",
            ]

            hover_tool = create_hover_tool(tooltip_item)
            fig.add_tools(hover_tool)
            self._set_legend(fig)

        div_element = self._create_div_element()
        write_bokeh_graph(bokeh.layouts.column([div_element, *figure_list]), output_file)

    def plot_quality_and_productivity(self, output_file: Path, worktime_type: WorktimeType, performance_unit: PerformanceUnit):
        """
        作業時間を元に算出した生産性と品質の関係を、メンバごとにプロットする
        """

        def create_figure(title: str, x_axis_label: str, y_axis_label: str) -> figure:
            return figure(
                width=self.PLOT_WIDTH,
                height=self.PLOT_HEIGHT,
                title=title,
                x_axis_label=x_axis_label,
                y_axis_label=y_axis_label,
            )

        def plot_average_and_quartile_line() -> None:
            x_average_hour = self._get_average_value(
                df,
                numerator_column=(f"{worktime_type.value}_worktime_hour", phase),
                denominator_column=(performance_unit.value, phase),
            )
            x_average_minute = x_average_hour * 60 if x_average_hour is not None else None

            for column_pair, fig in zip(
                [("rejected_count", "task_count"), ("pointed_out_inspection_comment_count", performance_unit.value)],
                figure_list,
            ):
                if x_average_minute is not None:
                    self._plot_average_line(fig, x_average_minute, dimension="height")

                y_average = self._get_average_value(
                    df,
                    numerator_column=(column_pair[0], phase),
                    denominator_column=(column_pair[1], phase),
                )
                if y_average is not None:
                    self._plot_average_line(fig, y_average, dimension="width")

            x_quartile = self._get_quartile_value(df, (f"{worktime_type.value}_worktime_minute/{performance_unit.value}", phase))
            for column, fig in zip(
                ["rejected_count/task_count", f"pointed_out_inspection_comment_count/{performance_unit.value}"],
                figure_list,
            ):
                if x_quartile is not None:
                    self._plot_quartile_line(fig, x_quartile, dimension="height")
                y_quartile = self._get_quartile_value(df, (column, phase))
                if y_quartile is not None:
                    self._plot_quartile_line(fig, y_quartile, dimension="width")

        def set_tooltip():
            for fig in figure_list:
                tooltip_item = [
                    "user_id_",
                    "username_",
                    "biography_",
                    f"{worktime_type.value}_worktime_hour_{phase}",
                    f"task_count_{phase}",
                    f"input_data_count_{phase}",
                    f"annotation_count_{phase}",
                    f"{worktime_type.value}_worktime_hour/input_data_count_{phase}",
                    f"{worktime_type.value}_worktime_hour/annotation_count_{phase}",
                    f"rejected_count_{phase}",
                    f"pointed_out_inspection_comment_count_{phase}",
                    f"rejected_count/task_count_{phase}",
                    f"pointed_out_inspection_comment_count/annotation_count_{phase}",
                    "first_working_date_",
                    "last_working_date_",
                    "working_days_",
                ]

                hover_tool = create_hover_tool(tooltip_item)
                fig.add_tools(hover_tool)
                self._set_legend(fig)

        if not self._validate_df_for_output(output_file):
            return

        # numpy.inf が含まれていると散布図を出力できないので置換する
        df = self.df.replace(numpy.inf, numpy.nan)
        for phase in self.phase_list:
            df[(f"{worktime_type.value}_worktime_minute/{performance_unit.value}", phase)] = (
                df[(f"{worktime_type.value}_worktime_hour/{performance_unit.value}", phase)] * 60
            )

        logger.debug(f"{output_file} を出力します。")

        performance_unit_name = performance_unit.performance_unit_name
        worktime_type_name = worktime_type.worktime_type_name
        figure_list = [
            create_figure(
                title=f"{performance_unit_name}あたり作業時間({worktime_type_name})とタスクあたり差し戻し回数の関係",
                x_axis_label=f"{performance_unit_name}あたり作業時間[minute/{performance_unit.value}]",
                y_axis_label="タスクあたり差し戻し回数",
            ),
            create_figure(
                title=f"{performance_unit_name}あたり作業時間({worktime_type_name})と{performance_unit_name}あたり検査コメント数の関係",
                x_axis_label=f"{performance_unit_name}あたり作業時間[minute/{performance_unit.value}]",
                y_axis_label=f"{performance_unit_name}あたり検査コメント数",
            ),
        ]
        column_pair_list = [
            (f"{worktime_type.value}_worktime_minute/{performance_unit.value}", "rejected_count/task_count"),
            (
                f"{worktime_type.value}_worktime_minute/{performance_unit.value}",
                f"pointed_out_inspection_comment_count/{performance_unit.value}",
            ),
        ]
        phase = TaskPhase.ANNOTATION.value
        df["biography"] = df["biography"].fillna("")

        # bokeh3.0.3では、string型の列を持つpandas.DataFrameを描画できないため、改めてobject型に戻す
        # TODO この問題が解決されたら、削除する
        # https://qiita.com/yuji38kwmt/items/b5da6ed521e827620186
        df = df.astype(
            {
                ("account_id", ""): "object",
                ("user_id", ""): "object",
                ("username", ""): "object",
                ("biography", ""): "object",
                ("first_working_date", ""): "object",
                ("last_working_date", ""): "object",
            }
        )

        for biography_index, biography in enumerate(sorted(set(df["biography"]))):
            for fig, column_pair in zip(figure_list, column_pair_list):
                x_column, y_column = column_pair
                filtered_df = df[(df["biography"] == biography) & df[(x_column, phase)].notna() & df[(y_column, phase)].notna()]
                if len(filtered_df) == 0:
                    continue
                source = ColumnDataSource(data=filtered_df)
                plot_bubble(
                    fig=fig,
                    source=source,
                    x_column_name=f"{x_column}_{phase}",
                    y_column_name=f"{y_column}_{phase}",
                    text_column_name="username_",
                    size_column_name=f"{worktime_type.value}_worktime_hour_{phase}",
                    legend_label=biography,
                    color=get_color_from_palette(biography_index),
                )

        plot_average_and_quartile_line()
        set_tooltip()

        div_element = self._create_div_element()
        div_element.text = div_element.text + """円の大きさ：作業時間<br>"""  # type: ignore[operator]
        write_bokeh_graph(bokeh.layouts.column([div_element, *figure_list]), output_file)
