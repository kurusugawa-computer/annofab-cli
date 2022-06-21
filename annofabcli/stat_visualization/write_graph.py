import argparse
import logging
from pathlib import Path
from typing import List, Optional

from annofabapi.models import TaskPhase

import annofabcli
from annofabcli.common.cli import get_list_from_args
from annofabcli.statistics.visualization.dataframe.cumulative_productivity import (
    AcceptorCumulativeProductivity,
    AnnotatorCumulativeProductivity,
    InspectorCumulativeProductivity,
)
from annofabcli.statistics.visualization.dataframe.productivity_per_date import (
    AcceptorProductivityPerDate,
    AnnotatorProductivityPerDate,
    InspectorProductivityPerDate,
)
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.project_dir import ProjectDir

logger = logging.getLogger(__name__)


class WritingGraph:
    def __init__(
        self,
        project_dir: ProjectDir,
        output_project_dir: ProjectDir,
        user_id_list: Optional[List[str]] = None,
        minimal_output: bool = False,
    ) -> None:
        self.project_dir = project_dir
        self.output_project_dir = output_project_dir
        self.user_id_list = user_id_list
        self.minimal_output = minimal_output

    def write_line_graph(self, task: Task):
        df = task.df.copy()

        self.output_project_dir.write_cumulative_line_graph(
            AnnotatorCumulativeProductivity(df),
            phase=TaskPhase.ANNOTATION,
            user_id_list=self.user_id_list,
            minimal_output=self.minimal_output,
        )
        self.output_project_dir.write_cumulative_line_graph(
            InspectorCumulativeProductivity(df),
            phase=TaskPhase.INSPECTION,
            user_id_list=self.user_id_list,
            minimal_output=self.minimal_output,
        )
        self.output_project_dir.write_cumulative_line_graph(
            AcceptorCumulativeProductivity(df),
            phase=TaskPhase.ACCEPTANCE,
            user_id_list=self.user_id_list,
            minimal_output=self.minimal_output,
        )

        if not self.minimal_output:
            annotator_per_date_obj = AnnotatorProductivityPerDate.from_df_task(task.df)
            inspector_per_date_obj = InspectorProductivityPerDate.from_df_task(task.df)
            acceptor_per_date_obj = AcceptorProductivityPerDate.from_df_task(task.df)

            self.output_project_dir.write_performance_line_graph_per_date(
                annotator_per_date_obj, phase=TaskPhase.ANNOTATION, user_id_list=self.user_id_list
            )
            self.output_project_dir.write_performance_line_graph_per_date(
                inspector_per_date_obj, phase=TaskPhase.INSPECTION, user_id_list=self.user_id_list
            )
            self.output_project_dir.write_performance_line_graph_per_date(
                acceptor_per_date_obj, phase=TaskPhase.ACCEPTANCE, user_id_list=self.user_id_list
            )

    def main(self):

        try:
            # メンバのパフォーマンスを散布図で出力する
            self.output_project_dir.write_user_performance_scatter_plot(self.project_dir.read_user_performance())
        except Exception:
            logger.warning("'メンバごとの生産性と品質.csv'から生成できるグラフの出力に失敗しました。", exc_info=True)

        try:
            task = self.project_dir.read_task_list()
            # ヒストグラムを出力
            self.output_project_dir.write_task_histogram(task)
            # ユーザごとにプロットした折れ線グラフを出力
            self.write_line_graph(task)
        except Exception:
            logger.warning("'タスクlist.csv'から生成できるグラフの出力に失敗しました。", exc_info=True)

        try:
            self.output_project_dir.write_whole_productivity_line_graph_per_date(
                self.project_dir.read_whole_productivity_per_date()
            )
        except Exception:
            logger.warning("'日毎の生産量と生産性.csv'から生成できるグラフの出力に失敗しました。", exc_info=True)

        try:
            self.output_project_dir.write_whole_productivity_line_graph_per_annotation_started_date(
                self.project_dir.read_whole_productivity_per_first_annotation_started_date()
            )
        except Exception:
            logger.warning("'教師付者_教師付開始日list.csv'から生成できるグラフの出力に失敗しました。", exc_info=True)

        try:
            self.output_project_dir.write_worktime_line_graph(self.project_dir.read_worktime_per_date_user())
        except Exception:
            logger.warning("'ユーザ_日付list-作業時間.csv'から生成できるグラフの出力に失敗しました。", exc_info=True)


def main(args):
    user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None
    main_obj = WritingGraph(
        project_dir=ProjectDir(args.dir),
        output_project_dir=ProjectDir(args.output_dir),
        minimal_output=args.minimal,
        user_id_list=user_id_list,
    )
    main_obj.main()


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help=f"``annofabcli statistics visualize`` コマンドの出力結果であるプロジェクトのディレクトリを指定してください。",  # noqa: E501
    )
    parser.add_argument(
        "-u",
        "--user_id",
        nargs="+",
        help=(
            "ユーザごとの折れ線グラフに表示するユーザのuser_idを指定してください。"
            "指定しない場合は、上位20人のユーザ情報がプロットされます。"
            " ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ。配下にプロジェクトディレクトリが生成されます。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "write_graph"
    subcommand_help = "`annofabcli statistics visualize` コマンドの出力結果であるプロジェクトのディレクトリから、グラフを出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help)
    parse_args(parser)
    return parser
