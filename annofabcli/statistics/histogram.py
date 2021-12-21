# pylint: disable=too-many-lines
import logging
from dataclasses import dataclass
from pathlib import Path

import holoviews as hv
import numpy as np
import pandas

logger = logging.getLogger(__name__)


def get_sub_title_from_series(ser: pandas.Series, decimals: int = 3) -> str:
    """pandas.Seriesから、平均値、標準偏差、データ数が記載されたSubTitleを生成する。"""
    mean = round(ser.mean(), decimals)
    std = round(ser.std(), decimals)
    sub_title = f"μ={mean}, α={std}, N={len(ser)}"
    return sub_title


hv.extension("bokeh")


@dataclass
class HistogramName:
    """
    ヒストグラムの名前を表現するデータクラス
    """

    title: str
    """グラフのタイトル"""
    x_axis_label: str
    """X軸のラベル名"""
    column: str
    """pandas.DataFrameにアクセスする列名"""
    y_axis_label: str = "タスク数"
    """Y軸のラベル名"""


class Histogram:
    """
    ヒストグラムを出力するクラス
    """

    def __init__(self, outdir: str):
        self.histogram_outdir = outdir
        Path(self.histogram_outdir).mkdir(exist_ok=True, parents=True)

    @staticmethod
    def _create_histogram(df: pandas.DataFrame, histogram_name: HistogramName, bins: int = 20) -> hv.Histogram:
        """
        ヒストグラムを生成する。
        Args:
            df:
            histogram_name:
            bins: ヒスグラムの棒の数

        Returns:
            ヒストグラムオブジェクト
        """
        mean = round(df[histogram_name.column].mean(), 3)
        std = round(df[histogram_name.column].std(), 3)
        title = f"{histogram_name.title}: μ={mean}, α={std}, N={len(df)}"

        data = df[histogram_name.column].values

        frequencies, edges = np.histogram(data, bins)
        hist = (
            hv.Histogram(
                (edges, frequencies), kdims=histogram_name.x_axis_label, vdims=histogram_name.y_axis_label, label=title
            )
            .options(width=500, title=title, fontsize={"title": 9, "labels": 9})
            .opts(hv.opts(tools=["hover"]))
        )
        return hist

    def _create_histogram_by_user(
        self, df: pandas.DataFrame, column: str, x_axis_label: str, username: str, user_id: str
    ) -> hv.Histogram:
        """
        ユーザごとにヒストグラムを作成する。

        Args:
            df:
            column:
            x_axis_label:
            username:
            user_id:

        Returns:

        """
        histogram_name = HistogramName(column=column, x_axis_label=x_axis_label, title=f"{username}({user_id})")
        hist = self._create_histogram(df, histogram_name=histogram_name)
        return hist

    def write_histogram_for_worktime(self, df: pandas.DataFrame):
        """
        作業時間に関する情報をヒストグラムとして表示する。

        Args:
            df: タスク一覧のDataFrame

        """
        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        renderer = hv.renderer("bokeh")

        output_file = f"{self.histogram_outdir}/ヒストグラム-作業時間"
        logger.debug(f"{output_file}.html を出力します。")

        histogram_name_list = [
            HistogramName(
                column="annotation_worktime_hour",
                x_axis_label="教師付時間[hour]",
                title="教師付時間",
            ),
            HistogramName(
                column="inspection_worktime_hour",
                x_axis_label="検査時間[hour]",
                title="検査時間",
            ),
            HistogramName(
                column="acceptance_worktime_hour",
                x_axis_label="受入時間[hour]",
                title="受入時間",
            ),
            HistogramName(column="sum_worktime_hour", x_axis_label="総作業時間[hour]", title="総作業時間"),
        ]

        histograms = []
        for histogram_name in histogram_name_list:
            filtered_df = df[df[histogram_name.column].notnull()]
            hist = self._create_histogram(filtered_df, histogram_name=histogram_name)
            histograms.append(hist)

        # 自動検査したタスクを除外して、検査時間をグラフ化する
        filtered_df = df[df["inspection_worktime_hour"].notnull()]
        histograms.append(
            self._create_histogram(
                filtered_df[~filtered_df["inspection_is_skipped"]],
                histogram_name=HistogramName(
                    column="inspection_worktime_hour",
                    x_axis_label="検査時間[hour]",
                    title="検査時間(自動検査されたタスクを除外)",
                ),
            )
        )

        # 自動受入したタスクを除外して、受入時間をグラフ化する
        filtered_df = df[df["acceptance_worktime_hour"].notnull()]
        histograms.append(
            self._create_histogram(
                filtered_df[~filtered_df["acceptance_is_skipped"]],
                histogram_name=HistogramName(
                    column="acceptance_worktime_hour",
                    x_axis_label="受入時間[hour]",
                    title="受入時間(自動受入されたタスクを除外)",
                ),
            )
        )

        # 軸範囲が同期しないようにする
        layout = hv.Layout(histograms).options(shared_axes=False).cols(3)
        renderer.save(layout, output_file)

    def write_histogram_for_other(self, df: pandas.DataFrame):
        """
        アノテーション数や、検査コメント数など、作業時間以外の情報をヒストグラムで表示する。

        Args:
            df: タスク一覧のDataFrame

        """
        if len(df) == 0:
            logger.info("タスク一覧が0件のため出力しない")
            return

        renderer = hv.renderer("bokeh")

        output_file = f"{self.histogram_outdir}/ヒストグラム"
        logger.debug(f"{output_file}.html を出力します。")

        histogram_name_list = [
            HistogramName(column="annotation_count", x_axis_label="アノテーション数", title="アノテーション数"),
            HistogramName(column="input_data_count", x_axis_label="画像枚数", title="画像枚数"),
            HistogramName(column="inspection_count", x_axis_label="検査コメント数", title="検査コメント数"),
            HistogramName(
                column="input_data_count_of_inspection",
                x_axis_label="指摘を受けた画像枚数",
                title="指摘を受けた画像枚数",
            ),
            # 経過日数
            HistogramName(
                column="diff_days_to_first_inspection_started",
                x_axis_label="最初の検査を着手するまでの日数",
                title="最初の検査を着手するまでの日数",
            ),
            HistogramName(
                column="diff_days_to_first_acceptance_started",
                x_axis_label="最初の受入を着手するまでの日数",
                title="最初の受入を着手するまでの日数",
            ),
            HistogramName(
                column="diff_days_to_task_completed",
                x_axis_label="受入完了状態になるまでの日数",
                title="受入完了状態になるまでの日数",
            ),
            # 差し戻し回数
            HistogramName(
                column="number_of_rejections_by_inspection",
                x_axis_label="検査フェーズでの差し戻し回数",
                title="検査フェーズでの差し戻し回数",
            ),
            HistogramName(
                column="number_of_rejections_by_acceptance",
                x_axis_label="受入フェーズでの差し戻し回数",
                title="受入フェーズでの差し戻し回数",
            ),
        ]

        histograms = []
        for histogram_name in histogram_name_list:
            filtered_df = df[df[histogram_name.column].notnull()]
            hist = self._create_histogram(filtered_df, histogram_name=histogram_name)
            histograms.append(hist)

        # 軸範囲が同期しないようにする
        layout = hv.Layout(histograms).options(shared_axes=False).cols(3)
        renderer.save(layout, output_file)
