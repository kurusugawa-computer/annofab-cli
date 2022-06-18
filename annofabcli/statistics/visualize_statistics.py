import argparse
import functools
import logging.handlers
import re
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Callable, Collection, List, Optional

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole, TaskPhase

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.stat_visualization.merge_visualization_dir import merge_visualization_dir
from annofabcli.statistics.database import Database, Query
from annofabcli.statistics.table import Table
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
from annofabcli.statistics.visualization.dataframe.project_performance import (
    ProjectPerformance,
    ProjectWorktimePerMonth,
)
from annofabcli.statistics.visualization.dataframe.task import Task
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance, WholePerformance
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.model import WorktimeColumn
from annofabcli.statistics.visualization.project_dir import ProjectDir, ProjectInfo

logger = logging.getLogger(__name__)


def get_project_output_dir(project_title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "__", project_title)


class WriteCsvGraph:
    task_df: Optional[pandas.DataFrame] = None
    task_history_df: Optional[pandas.DataFrame] = None

    def __init__(
        self,
        service: annofabapi.Resource,
        project_id: str,
        table_obj: Table,
        output_dir: Path,
        df_labor: Optional[pandas.DataFrame],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        minimal_output: bool = False,
        output_only_text: bool = False,
    ):
        self.service = service
        self.project_id = project_id
        self.output_dir = output_dir
        self.table_obj = table_obj
        self.df_labor = df_labor
        self.start_date = start_date
        self.end_date = end_date
        self.minimal_output = minimal_output
        self.output_only_text = output_only_text

        self.project_dir = ProjectDir(output_dir)

    def _catch_exception(self, function: Callable[..., Any]) -> Callable[..., Any]:
        """
        Exceptionをキャッチしてログにstacktraceを出力する。
        """

        def wrapped(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(f"project_id: {self.project_id}, exception: {e}")
                logger.exception(e)
                return None

        return wrapped

    def _get_task_df(self) -> pandas.DataFrame:
        if self.task_df is None:
            self.task_df = self.table_obj.create_task_df()
        return self.task_df

    def _get_task_history_df(self) -> pandas.DataFrame:
        if self.task_history_df is None:
            self.task_history_df = self.table_obj.create_task_history_df()
        return self.task_history_df

    def write_task_info(self) -> None:
        """
        タスクに関するヒストグラムを出力する。

        """
        obj = Task(self._get_task_df())

        self.project_dir.write_task_list(obj)

        if not self.output_only_text:
            self.project_dir.write_task_histogram(obj)

    def write_user_performance(self) -> None:
        """
        ユーザごとの生産性と品質に関する情報を出力する。
        """

        df_task_history = self._get_task_history_df()
        annotation_count_ratio_df = self.table_obj.create_annotation_count_ratio_df(
            df_task_history, self._get_task_df()
        )
        if len(annotation_count_ratio_df) == 0:
            user_performance = UserPerformance(pandas.DataFrame())
        else:
            user_performance = UserPerformance.from_df(
                df_task_history=df_task_history,
                df_labor=self.df_labor,
                df_worktime_ratio=annotation_count_ratio_df,
            )

        self.project_dir.write_user_performance(user_performance)

        whole_performance = WholePerformance.from_user_performance(user_performance)
        self.project_dir.write_whole_performance(whole_performance)

        if not self.output_only_text:
            self.project_dir.write_user_performance_scatter_plot(user_performance)

    def write_cumulative_linegraph_by_user(self, user_id_list: Optional[List[str]] = None) -> None:
        """ユーザごとの累積折れ線グラフをプロットする。"""
        df_task = self._get_task_df()

        annotator_obj = AnnotatorCumulativeProductivity(df_task)
        inspector_obj = InspectorCumulativeProductivity(df_task)
        acceptor_obj = AcceptorCumulativeProductivity(df_task)

        if not self.output_only_text:

            self.project_dir.write_cumulative_line_graph(
                annotator_obj, phase=TaskPhase.ANNOTATION, user_id_list=user_id_list, minimal_output=self.minimal_output
            )
            self.project_dir.write_cumulative_line_graph(
                inspector_obj, phase=TaskPhase.INSPECTION, user_id_list=user_id_list, minimal_output=self.minimal_output
            )
            self.project_dir.write_cumulative_line_graph(
                acceptor_obj, phase=TaskPhase.ACCEPTANCE, user_id_list=user_id_list, minimal_output=self.minimal_output
            )

    def write_worktime_per_date(self, user_id_list: Optional[List[str]] = None) -> None:
        """日ごとの作業時間情報を出力する。"""
        worktime_per_date_obj = WorktimePerDate.from_webapi(
            self.service, self.project_id, self.df_labor, start_date=self.start_date, end_date=self.end_date
        )

        self.project_dir.write_worktime_per_date_user(worktime_per_date_obj)

        df_task = self._get_task_df()
        productivity_per_completed_date_obj = WholeProductivityPerCompletedDate.from_df(
            df_task, worktime_per_date_obj.df
        )

        self.project_dir.write_whole_productivity_per_date(productivity_per_completed_date_obj)

        productivity_per_started_date_obj = WholeProductivityPerFirstAnnotationStartedDate.from_df(df_task)
        self.project_dir.write_whole_productivity_per_first_annotation_started_date(productivity_per_started_date_obj)

        if not self.output_only_text:
            self.project_dir.write_worktime_line_graph(worktime_per_date_obj, user_id_list=user_id_list)
            self.project_dir.write_whole_productivity_line_graph_per_date(productivity_per_completed_date_obj)
            self.project_dir.write_whole_productivity_line_graph_per_annotation_started_date(
                productivity_per_started_date_obj
            )

    def write_user_productivity_per_date(self, user_id_list: Optional[List[str]] = None):
        """ユーザごとの日ごとの生産性情報を出力する。"""
        df_task = self._get_task_df()

        annotator_per_date_obj = AnnotatorProductivityPerDate.from_df_task(df_task)
        inspector_per_date_obj = InspectorProductivityPerDate.from_df_task(df_task)
        acceptor_per_date_obj = AcceptorProductivityPerDate.from_df_task(df_task)

        # 開始日ごとのCSVを出力
        self.project_dir.write_performance_per_started_date_csv(annotator_per_date_obj, phase=TaskPhase.ANNOTATION)
        self.project_dir.write_performance_per_started_date_csv(inspector_per_date_obj, phase=TaskPhase.INSPECTION)
        self.project_dir.write_performance_per_started_date_csv(acceptor_per_date_obj, phase=TaskPhase.ACCEPTANCE)

        if not self.output_only_text:
            self.project_dir.write_performance_line_graph_per_date(
                annotator_per_date_obj, phase=TaskPhase.ANNOTATION, user_id_list=user_id_list
            )
            self.project_dir.write_performance_line_graph_per_date(
                inspector_per_date_obj, phase=TaskPhase.INSPECTION, user_id_list=user_id_list
            )
            self.project_dir.write_performance_line_graph_per_date(
                acceptor_per_date_obj, phase=TaskPhase.ACCEPTANCE, user_id_list=user_id_list
            )


class VisualizingStatisticsMain:
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        temp_dir: Path,
        # タスクの絞り込み関係
        task_query: Optional[TaskQuery],
        task_ids: Optional[Collection[str]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        # 出力方法
        minimal_output: bool = False,
        output_only_text: bool = False,
        # その他
        download_latest: bool = False,
        is_get_task_histories_one_of_each: bool = False,
        df_labor: Optional[pandas.DataFrame],
        user_ids: Optional[List[str]],
    ):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.temp_dir = temp_dir

        self.task_query = task_query
        self.task_ids = task_ids
        self.start_date = start_date
        self.end_date = end_date
        self.minimal_output = minimal_output
        self.output_only_text = output_only_text
        self.download_latest = download_latest
        self.is_get_task_histories_one_of_each = is_get_task_histories_one_of_each
        self.df_labor = df_labor
        self.user_ids = user_ids

    def write_project_info_json(self, project_id: str, project_dir: ProjectDir):
        """
        プロジェクト情報をJSONファイルに出力します。
        """
        project_info = self.service.api.get_project(project_id)[0]
        project_title = project_info["title"]
        logger.info(f"project_title = {project_title}")

        project_summary = ProjectInfo(
            project_id=project_id,
            project_title=project_title,
            input_data_type=project_info["input_data_type"],
            measurement_datetime=annofabapi.utils.str_now(),
            query=Query(
                task_query=self.task_query, task_ids=self.task_ids, start_date=self.start_date, end_date=self.end_date
            ),
        )
        project_dir.write_project_info(project_summary)

    def visualize_statistics(
        self,
        project_id: str,
        output_project_dir: Path,
    ):
        """
        プロジェクトの統計情報を出力する。

        Args:
            project_id: 対象のproject_id
            task_query: タスク検索クエリ

        """

        self.facade.validate_project(
            project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER]
        )

        project_dir = ProjectDir(output_project_dir)
        self.write_project_info_json(project_id=project_id, project_dir=project_dir)

        database = Database(
            self.service,
            project_id,
            self.temp_dir,
            query=Query(
                task_query=self.task_query,
                task_ids=set(self.task_ids) if self.task_ids is not None else None,
                start_date=self.start_date,
                end_date=self.end_date,
            ),
        )
        database.update_db(
            self.download_latest, is_get_task_histories_one_of_each=self.is_get_task_histories_one_of_each
        )

        table_obj = Table(database)
        if len(table_obj._get_task_list()) == 0:
            logger.warning(f"project_id={project_id}: タスク一覧が0件なのでファイルを出力しません。終了します。")
            return
        if len(table_obj._get_task_histories_dict().keys()) == 0:
            logger.warning(f"project_id={project_id}: タスク履歴一覧が0件なのでファイルを出力しません。終了します。")
            return

        if self.df_labor is not None:
            # project_id列がある場合（複数のproject_id列を指定した場合）はproject_idで絞り込む
            if "project_id" in self.df_labor:
                df_labor = self.df_labor[self.df_labor["project_id"] == project_id]
            else:
                df_labor = self.df_labor
            if self.start_date is not None:
                df_labor = df_labor[df_labor["date"] >= self.start_date]
            if self.end_date is not None:
                df_labor = df_labor[df_labor["date"] <= self.end_date]

        else:
            df_labor = None

        write_obj = WriteCsvGraph(
            self.service,
            project_id,
            table_obj,
            output_project_dir,
            df_labor=df_labor,
            start_date=self.start_date,
            end_date=self.end_date,
            minimal_output=self.minimal_output,
            output_only_text=self.output_only_text,
        )

        write_obj._catch_exception(write_obj.write_user_performance)()

        write_obj._catch_exception(write_obj.write_task_info)()

        # 折れ線グラフ
        write_obj.write_cumulative_linegraph_by_user(self.user_ids)

        write_obj._catch_exception(write_obj.write_worktime_per_date)(self.user_ids)

        if not self.minimal_output:
            write_obj._catch_exception(write_obj.write_user_productivity_per_date)(self.user_ids)

    def visualize_statistics_wrapper(
        self,
        project_id: str,
        root_output_dir: Path,
    ) -> Optional[Path]:
        try:
            project_title = self.facade.get_project_title(project_id)
            output_project_dir = root_output_dir / get_project_output_dir(project_title)
            self.visualize_statistics(
                project_id=project_id,
                output_project_dir=output_project_dir,
            )
            return output_project_dir
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"project_id='{project_id}'の可視化処理に失敗しました。", exc_info=True)
            return None

    def visualize_statistics_for_project_list(
        self,
        project_id_list: List[str],
        root_output_dir: Path,
        *,
        parallelism: Optional[int] = None,
    ) -> List[Path]:

        output_project_dir_list: List[Path] = []

        wrap = functools.partial(self.visualize_statistics_wrapper, root_output_dir=root_output_dir)
        if parallelism is not None:
            with Pool(parallelism) as pool:
                result_list = pool.map(wrap, project_id_list)
                output_project_dir_list = [e for e in result_list if e is not None]
        else:
            for project_id in project_id_list:
                output_project_dir = wrap(project_id)
                if output_project_dir is not None:
                    output_project_dir_list.append(output_project_dir)

        return output_project_dir_list


class VisualizeStatistics(AbstractCommandLineInterface):
    """
    統計情報を可視化する。
    """

    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli statistics visualize: error:"
        if args.start_date is not None and args.end_date is not None:
            if args.start_date > args.end_date:
                print(
                    f"{COMMON_MESSAGE} argument `START_DATE <= END_DATE` の関係を満たしていません。",
                    file=sys.stderr,
                )
                return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None

        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id) if args.user_id is not None else None
        project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)

        root_output_dir: Path = args.output_dir

        if args.labor_csv is None:
            logger.warning(f"'--labor_csv'が指定されていないので、実績作業時間に関する情報は出力されません。")

        df_labor = pandas.read_csv(args.labor_csv) if args.labor_csv is not None else None

        with tempfile.TemporaryDirectory() as str_temp_dir:

            main_obj = VisualizingStatisticsMain(
                service=self.service,
                temp_dir=Path(str_temp_dir),
                task_query=task_query,
                task_ids=task_id_list,
                user_ids=user_id_list,
                df_labor=df_labor,
                download_latest=args.latest,
                is_get_task_histories_one_of_each=args.get_task_histories_one_of_each,
                start_date=args.start_date,
                end_date=args.end_date,
                minimal_output=args.minimal,
                output_only_text=args.output_only_text,
            )

        if len(project_id_list) == 1:
            main_obj.visualize_statistics(project_id_list[0], root_output_dir)
            if args.merge:
                logger.warning(f"出力した統計情報は1件以下なので、`merge`ディレクトリを出力しません。")

        else:
            # project_idが複数指定された場合は、project_titleのディレクトリに統計情報を出力する
            output_project_dir_list = main_obj.visualize_statistics_for_project_list(
                project_id_list=project_id_list,
                root_output_dir=root_output_dir,
                parallelism=args.parallelism,
            )

            if args.merge:
                merge_visualization_dir(
                    project_dir_list=[ProjectDir(e) for e in output_project_dir_list],
                    output_project_dir=ProjectDir(root_output_dir / "merge"),
                    user_id_list=user_id_list,
                    minimal_output=args.minimal,
                )

            if len(output_project_dir_list) > 0:
                project_dir_list = [ProjectDir(e) for e in output_project_dir_list]
                project_performance = ProjectPerformance.from_project_dirs(project_dir_list)
                project_performance.to_csv(root_output_dir / "プロジェクトごとの生産性と品質.csv")

                project_actual_worktime = ProjectWorktimePerMonth.from_project_dirs(
                    project_dir_list, WorktimeColumn.ACTUAL_WORKTIME_HOUR
                )
                project_actual_worktime.to_csv(root_output_dir / "プロジェクごとの毎月の実績作業時間.csv")

                project_monitored_worktime = ProjectWorktimePerMonth.from_project_dirs(
                    project_dir_list, WorktimeColumn.MONITORED_WORKTIME_HOUR
                )
                project_monitored_worktime.to_csv(root_output_dir / "プロジェクごとの毎月の計測作業時間.csv")

            else:
                logger.warning(f"出力した統計情報は0件なので、`プロジェクトごとの生産性と品質.csv`を出力しません。")


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeStatistics(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument(
        "-p",
        "--project_id",
        required=True,
        nargs="+",
        help=(
            "対象のプロジェクトのproject_idを指定してください。複数指定した場合、プロジェクトごとに統計情報が出力されます。\n"
            "``file://`` を先頭に付けると、project_idが記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリのパスを指定してください。")

    parser.add_argument(
        "-u",
        "--user_id",
        nargs="+",
        help=(
            "メンバごとの統計グラフに表示するユーザのuser_idを指定してください。"
            "指定しない場合は、上位20人が表示されます。\n"
            "``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="タスクの検索クエリをJSON形式で指定します。指定しない場合はすべてのタスクを取得します。\n"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        "クエリのキーは、``task_id`` , ``phase`` , ``phase_stage`` , ``status`` のみです。",
    )

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        required=False,
        nargs="+",
        help="集計対象のタスクのtask_idを指定します。\n" + "``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--start_date", type=str, help="指定した日付（ ``YYYY-MM-DD`` ）以降に教師付を開始したタスクから生産性を算出します。")
    parser.add_argument("--end_date", type=str, help="指定した日付（ ``YYYY-MM-DD`` ）以前に更新されたタスクから生産性を算出します。")

    parser.add_argument(
        "--latest",
        action="store_true",
        help="統計情報の元になるファイル（アノテーションzipなど）の最新版を参照します。このオプションを指定すると、各ファイルを更新するのに5分以上待ちます。\n"
        "ただしWebAPIの都合上、'タスク履歴全件ファイル'は最新版を参照できません。タスク履歴の最新版を参照する場合は ``--get_task_histories_one_of_each`` を指定してください。",
    )

    parser.add_argument(
        "--get_task_histories_one_of_each",
        action="store_true",
        help="タスク履歴を1個ずつ取得して、タスク履歴の最新版を参照します。タスクの数だけWebAPIを実行するので、処理時間が長くなります。",
    )

    parser.add_argument(
        "--labor_csv",
        type=Path,
        help=(
            "実績作業時間情報が格納されたCSVを指定してください。指定しない場合は、実績作業時間は0とみなします。列名は以下の通りです。\n"
            "\n"
            "* date\n"
            "* account_id\n"
            "* actual_worktime_hour\n"
            "* project_id (optional: ``--project_id`` に複数の値を指定したときは必須です) \n"
        ),
    )

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    parser.add_argument(
        "--output_only_text",
        action="store_true",
        help="テキストファイルのみ出力します。グラフが掲載されているHTMLファイルは出力しません。",
    )

    parser.add_argument(
        "--merge",
        action="store_true",
        help="指定した場合、複数のproject_idを指定したときに、マージした統計情報も出力します。ディレクトリ名は ``merge`` です。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        help="並列度。 ``--project_id`` に複数のproject_idを指定したときのみ有効なオプションです。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "visualize"
    subcommand_help = "生産性に関するCSVファイルやグラフを出力します。"
    description = "生産性に関するCSVファイルやグラフを出力します。"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
