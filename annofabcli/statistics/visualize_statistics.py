import argparse
import importlib
import logging.handlers
import re
import sys
from dataclasses import dataclass
from functools import partial
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Callable, Collection, List, Optional

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole
from dataclasses_json import DataClassJsonMixin

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import TaskQuery
from annofabcli.stat_visualization.merge_visualization_dir import merge_visualization_dir
from annofabcli.statistics.csv import (
    FILENAME_PERFORMANCE_PER_DATE,
    FILENAME_PERFORMANCE_PER_USER,
    FILENAME_WHOLE_PERFORMANCE,
    Csv,
)
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
from annofabcli.statistics.visualization.dataframe.user_performance import (
    ProjectPerformance,
    UserPerformance,
    WholePerformance,
)
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate

logger = logging.getLogger(__name__)


@dataclass
class CommnadLineArgs(DataClassJsonMixin):
    task_query: TaskQuery
    user_id_list: Optional[List[str]]
    start_date: Optional[str]
    end_date: Optional[str]
    ignored_task_id_list: Optional[List[str]]


@dataclass
class ProjectSummary(DataClassJsonMixin):
    project_id: str
    project_title: str
    measurement_datetime: str
    """計測日時。（2004-04-01T12:00+09:00形式）"""
    args: CommnadLineArgs
    """コマンドライン引数"""


def write_project_performance_csv(project_dirs: Collection[Path], output_path: Path):
    csv_file_list = [e / FILENAME_WHOLE_PERFORMANCE for e in project_dirs]

    obj_list = []
    project_title_list = []
    for csv_file in csv_file_list:
        if csv_file.exists():
            obj_list.append(WholePerformance.from_csv(csv_file))
            project_title_list.append(csv_file.parent.name)
        else:
            logger.warning(f"{csv_file} は存在しないのでスキップします。")

    main_obj = ProjectPerformance.from_whole_performance_objs(obj_list, project_title_list)
    main_obj.to_csv(output_path)


def write_project_name_file(
    annofab_service: annofabapi.Resource, project_id: str, command_line_args: CommnadLineArgs, output_project_dir: Path
):
    """
    ファイル名がプロジェクト名のjsonファイルを生成する。
    """
    project_info = annofab_service.api.get_project(project_id)[0]
    project_title = project_info["title"]
    logger.info(f"project_title = {project_title}")
    filename = annofabcli.utils.to_filename(project_title)
    output_project_dir.mkdir(exist_ok=True, parents=True)

    project_summary = ProjectSummary(
        project_id=project_id,
        project_title=project_title,
        measurement_datetime=annofabapi.utils.str_now(),
        args=command_line_args,
    )

    with open(str(output_project_dir / f"{filename}.json"), "w", encoding="utf-8") as f:
        f.write(project_summary.to_json(ensure_ascii=False, indent=2))


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
        minimal_output: bool = False,
    ):
        self.service = service
        self.project_id = project_id
        self.output_dir = output_dir
        self.table_obj = table_obj
        self.csv_obj = Csv(str(output_dir))
        # holoviews のloadに時間がかかって、helpコマンドの出力が遅いため、遅延ロードする
        histogram_module = importlib.import_module("annofabcli.statistics.histogram")
        self.histogram_obj = histogram_module.Histogram(str(output_dir / "histogram"))  # type: ignore

        self.df_labor = self.table_obj.create_labor_df(df_labor)
        self.minimal_output = minimal_output

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

    def _get_task_df(self):
        if self.task_df is None:
            self.task_df = self.table_obj.create_task_df()
        return self.task_df

    def _get_task_history_df(self):
        if self.task_history_df is None:
            self.task_history_df = self.table_obj.create_task_history_df()
        return self.task_history_df

    def write_histogram_for_task(self) -> None:
        """
        タスクに関するヒストグラムを出力する。

        """
        task_df = self._get_task_df()
        self._catch_exception(self.histogram_obj.write_histogram_for_worktime)(task_df)
        self._catch_exception(self.histogram_obj.write_histogram_for_other)(task_df)

    def write_user_performance(self) -> None:
        """
        ユーザごとの生産性と品質に関する情報を出力する。
        """

        df_task_history = self._get_task_history_df()
        annotation_count_ratio_df = self.table_obj.create_annotation_count_ratio_df(
            df_task_history, self._get_task_df()
        )
        if len(annotation_count_ratio_df) == 0:
            obj = UserPerformance(pandas.DataFrame())
        else:
            obj = UserPerformance.from_df(
                df_task_history=df_task_history,
                df_labor=self.df_labor,
                df_worktime_ratio=annotation_count_ratio_df,
            )

        obj.to_csv(self.output_dir / FILENAME_PERFORMANCE_PER_USER)
        WholePerformance(obj.get_summary()).to_csv(self.output_dir / FILENAME_WHOLE_PERFORMANCE)

        obj.plot_quality(self.output_dir / "scatter/散布図-教師付者の品質と作業量の関係.html")
        obj.plot_productivity_from_monitored_worktime(
            self.output_dir / "scatter/散布図-アノテーションあたり作業時間と累計作業時間の関係-計測時間.html"
        )
        obj.plot_quality_and_productivity_from_monitored_worktime(
            self.output_dir / "scatter/散布図-アノテーションあたり作業時間と品質の関係-計測時間-教師付者用.html"
        )

        if obj.actual_worktime_exists():
            obj.plot_productivity_from_actual_worktime(
                self.output_dir / "scatter/散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間.html"
            )
            obj.plot_quality_and_productivity_from_actual_worktime(
                self.output_dir / "scatter/散布図-アノテーションあたり作業時間と品質の関係-実績時間-教師付者用.html"
            )
        else:
            logger.warning(
                f"実績作業時間の合計値が0なので、実績作業時間関係の以下のグラフは出力しません。\n"
                " * '散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間.html'\n"
                " * '散布図-アノテーションあたり作業時間と品質の関係-実績時間-教師付者用'"
            )

    def write_whole_productivity_per_date(self) -> None:
        """日ごとの全体の生産性に関するファイルを出力する。"""
        task_df = self._get_task_df()
        whole_productivity_df = WholeProductivityPerCompletedDate.create(task_df, self.df_labor)

        WholeProductivityPerCompletedDate.plot(whole_productivity_df, self.output_dir / "line-graph/折れ線-横軸_日-全体.html")
        WholeProductivityPerCompletedDate.plot_cumulatively(
            whole_productivity_df, self.output_dir / "line-graph/累積折れ線-横軸_日-全体.html"
        )

        WholeProductivityPerCompletedDate.to_csv(whole_productivity_df, self.output_dir / FILENAME_PERFORMANCE_PER_DATE)

    def write_whole_productivity_per_first_annotation_started_date(self) -> None:
        df = WholeProductivityPerFirstAnnotationStartedDate.create(self.task_df)
        WholeProductivityPerFirstAnnotationStartedDate.to_csv(df, self.output_dir / "教師付開始日毎の生産量と生産性.csv")
        WholeProductivityPerFirstAnnotationStartedDate.plot(df, self.output_dir / "line-graph/折れ線-横軸_教師付開始日-全体.html")

    def write_cumulative_linegraph_by_user(self, user_id_list: Optional[List[str]] = None) -> None:
        """ユーザごとの累積折れ線グラフをプロットする。"""
        df_task = self._get_task_df()

        annotator_obj = AnnotatorCumulativeProductivity(df_task)
        inspector_obj = InspectorCumulativeProductivity(df_task)
        acceptor_obj = AcceptorCumulativeProductivity(df_task)

        annotator_obj.plot_annotation_metrics(
            self.output_dir / "line-graph/教師付者用/累積折れ線-横軸_アノテーション数-教師付者用.html", user_id_list
        )
        inspector_obj.plot_annotation_metrics(
            self.output_dir / "line-graph/検査者用/累積折れ線-横軸_アノテーション数-検査者用.html", user_id_list
        )
        acceptor_obj.plot_annotation_metrics(
            self.output_dir / "line-graph/受入者用/累積折れ線-横軸_アノテーション数-受入者用.html", user_id_list
        )

        if not self.minimal_output:
            annotator_obj.plot_input_data_metrics(
                self.output_dir / "line-graph/教師付者用/累積折れ線-横軸_入力データ数-教師付者用.html", user_id_list
            )
            inspector_obj.plot_input_data_metrics(
                self.output_dir / "line-graph/検査者用/累積折れ線-横軸_入力データ数-検査者用.html", user_id_list
            )
            acceptor_obj.plot_input_data_metrics(
                self.output_dir / "line-graph/受入者用/累積折れ線-横軸_入力データ数-受入者用.html", user_id_list
            )

            annotator_obj.plot_task_metrics(self.output_dir / "line-graph/教師付者用/累積折れ線-横軸_タスク数-教師付者用.html", user_id_list)

    def write_worktime_per_date(
        self, user_id_list: Optional[List[str]] = None, df_labor: Optional[pandas.DataFrame] = None
    ) -> None:
        """日ごとの作業時間情報を出力する。"""
        obj = WorktimePerDate.from_webapi(self.service, self.project_id, df_labor)
        obj.plot_cumulatively(self.output_dir / "line-graph/累積折れ線-横軸_日-縦軸_作業時間.html", user_id_list)
        obj.to_csv(self.output_dir / "ユーザ_日付list-作業時間.csv")

    def write_csv_for_task(self) -> None:
        """
        タスク関係のCSVを出力する。
        """
        task_df = self._get_task_df()
        self._catch_exception(self.csv_obj.write_task_list)(task_df, dropped_columns=["input_data_id_list"])

    def write_user_productivity_per_date(self, user_id_list: Optional[List[str]] = None):
        """ユーザごとの日ごとの生産性情報を出力する。"""
        # 各ユーザごとの日ごとの情報
        df_task = self._get_task_df()
        annotator_per_date_obj = AnnotatorProductivityPerDate.from_df_task(df_task)
        annotator_per_date_obj.to_csv(self.output_dir / Path("教師付者_教師付開始日list.csv"))
        annotator_per_date_obj.plot_annotation_metrics(
            self.output_dir / Path("line-graph/教師付者用/折れ線-横軸_教師付開始日-縦軸_アノテーション単位の指標-教師付者用.html"), user_id_list
        )
        annotator_per_date_obj.plot_input_data_metrics(
            self.output_dir / Path("line-graph/教師付者用/折れ線-横軸_教師付開始日-縦軸_入力データ単位の指標-教師付者用.html"), user_id_list
        )

        inspector_per_date_obj = InspectorProductivityPerDate.from_df_task(df_task)
        inspector_per_date_obj.to_csv(self.output_dir / Path("検査者_検査開始日list.csv"))
        inspector_per_date_obj.plot_annotation_metrics(
            self.output_dir / Path("line-graph/検査者用/折れ線-横軸_検査開始日-縦軸_アノテーション単位の指標-検査者用.html"), user_id_list
        )
        inspector_per_date_obj.plot_input_data_metrics(
            self.output_dir / Path("line-graph/検査者用/折れ線-横軸_検査開始日-縦軸_入力データ単位の指標-検査者用.html"), user_id_list
        )

        acceptor_per_date = AcceptorProductivityPerDate.from_df_task(df_task)
        acceptor_per_date.to_csv(self.output_dir / Path("受入者_受入開始日list.csv"))
        acceptor_per_date.plot_annotation_metrics(
            self.output_dir / Path("line-graph/検査者用/折れ線-横軸_検査開始日-縦軸_アノテーション単位の指標-検査者用.html"), user_id_list
        )
        acceptor_per_date.plot_input_data_metrics(
            self.output_dir / Path("line-graph/検査者用/折れ線-横軸_検査開始日-縦軸_入力データ単位の指標-検査者用.html"), user_id_list
        )


def visualize_statistics(
    project_id: str,
    *,
    annofab_service: annofabapi.Resource,
    annofab_facade: AnnofabApiFacade,
    work_dir: Path,
    output_project_dir: Path,
    task_query: TaskQuery,
    df_labor: Optional[pandas.DataFrame],
    task_id_list: Optional[List[str]],
    ignored_task_id_list: Optional[List[str]],
    user_id_list: Optional[List[str]],
    update: bool = False,
    download_latest: bool = False,
    is_get_task_histories_one_of_each: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    is_get_labor: bool = False,
    minimal_output: bool = False,
):
    """
    プロジェクトの統計情報を出力する。

    Args:
        project_id: 対象のproject_id
        task_query: タスク検索クエリ

    """

    annofab_facade.validate_project(
        project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER]
    )

    checkpoint_dir = work_dir / project_id
    checkpoint_dir.mkdir(exist_ok=True, parents=True)

    database = Database(
        annofab_service,
        project_id,
        str(checkpoint_dir),
        query=Query(
            task_query=task_query,
            task_id_set=set(task_id_list) if task_id_list is not None else None,
            ignored_task_id_set=set(ignored_task_id_list) if ignored_task_id_list is not None else None,
            start_date=start_date,
            end_date=end_date,
        ),
        is_get_labor=is_get_labor,
    )
    if update:
        database.update_db(download_latest, is_get_task_histories_one_of_each=is_get_task_histories_one_of_each)

    table_obj = Table(database, ignored_task_id_list)
    if len(table_obj._get_task_list()) == 0:
        logger.warning(f"project_id={project_id}: タスク一覧が0件なのでファイルを出力しません。終了します。")
        return
    if len(table_obj._get_task_histories_dict().keys()) == 0:
        logger.warning(f"project_id={project_id}: タスク履歴一覧が0件なのでファイルを出力しません。終了します。")
        return

    write_project_name_file(
        annofab_service,
        project_id=project_id,
        command_line_args=CommnadLineArgs(
            task_query=task_query,
            user_id_list=user_id_list,
            start_date=start_date,
            end_date=end_date,
            ignored_task_id_list=ignored_task_id_list,
        ),
        output_project_dir=output_project_dir,
    )
    write_obj = WriteCsvGraph(
        annofab_service, project_id, table_obj, output_project_dir, df_labor=df_labor, minimal_output=minimal_output
    )
    write_obj.write_csv_for_task()

    write_obj._catch_exception(write_obj.write_user_performance)()

    # ヒストグラム
    write_obj.write_histogram_for_task()

    # 折れ線グラフ
    write_obj.write_cumulative_linegraph_by_user(user_id_list)
    write_obj.write_whole_productivity_per_date()

    write_obj.write_whole_productivity_per_first_annotation_started_date()

    if not minimal_output:
        write_obj._catch_exception(write_obj.write_worktime_per_date)(user_id_list, df_labor=df_labor)

        write_obj._catch_exception(write_obj.write_user_productivity_per_date)(user_id_list)


def visualize_statistics_wrapper(
    project_id: str,
    *,
    root_output_dir: Path,
    annofab_service: annofabapi.Resource,
    annofab_facade: AnnofabApiFacade,
    work_dir: Path,
    task_query: TaskQuery,
    df_labor: Optional[pandas.DataFrame],
    task_id_list: Optional[List[str]],
    ignored_task_id_list: Optional[List[str]],
    user_id_list: Optional[List[str]],
    update: bool = False,
    download_latest: bool = False,
    is_get_task_histories_one_of_each: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    minimal_output: bool = False,
    is_get_labor: bool = False,
) -> Optional[Path]:

    try:
        df_sub_labor = df_labor[df_labor["project_id"] == project_id] if df_labor is not None else None
        project_title = annofab_facade.get_project_title(project_id)
        output_project_dir = root_output_dir / get_project_output_dir(project_title)

        visualize_statistics(
            annofab_service=annofab_service,
            annofab_facade=annofab_facade,
            project_id=project_id,
            work_dir=work_dir,
            output_project_dir=output_project_dir,
            task_query=task_query,
            df_labor=df_sub_labor,
            task_id_list=task_id_list,
            ignored_task_id_list=ignored_task_id_list,
            user_id_list=user_id_list,
            update=update,
            download_latest=download_latest,
            is_get_task_histories_one_of_each=is_get_task_histories_one_of_each,
            start_date=start_date,
            end_date=end_date,
            minimal_output=minimal_output,
            is_get_labor=is_get_labor,
        )
        return output_project_dir
    except Exception:  # pylint: disable=broad-except
        logger.warning(f"project_id={project_id}の統計情報の出力に失敗しました。", exc_info=True)
        return None


class VisualizeStatistics(AbstractCommandLineInterface):
    """
    統計情報を可視化する。
    """

    def visualize_statistics_for_project_list(
        self,
        *,
        root_output_dir: Path,
        project_id_list: List[str],
        work_dir: Path,
        task_query: TaskQuery,
        df_labor: Optional[pandas.DataFrame],
        task_id_list: Optional[List[str]],
        ignored_task_id_list: Optional[List[str]],
        user_id_list: Optional[List[str]],
        update: bool = False,
        download_latest: bool = False,
        is_get_task_histories_one_of_each: bool = False,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        minimal_output: bool = False,
        is_get_labor: bool = False,
        parallelism: Optional[int] = None,
    ) -> List[Path]:
        output_project_dir_list: List[Path] = []

        if parallelism is not None:
            partial_func = partial(
                visualize_statistics_wrapper,
                root_output_dir=root_output_dir,
                annofab_service=self.service,
                annofab_facade=self.facade,
                work_dir=work_dir,
                task_query=task_query,
                df_labor=df_labor,
                task_id_list=task_id_list,
                ignored_task_id_list=ignored_task_id_list,
                user_id_list=user_id_list,
                update=update,
                download_latest=download_latest,
                is_get_task_histories_one_of_each=is_get_task_histories_one_of_each,
                start_date=start_date,
                end_date=end_date,
                minimal_output=minimal_output,
                is_get_labor=is_get_labor,
            )
            with Pool(parallelism) as pool:
                result_list = pool.map(partial_func, project_id_list)
                output_project_dir_list = [e for e in result_list if e is not None]

        else:

            for project_id in project_id_list:
                output_project_dir = visualize_statistics_wrapper(
                    root_output_dir=root_output_dir,
                    annofab_service=self.service,
                    annofab_facade=self.facade,
                    project_id=project_id,
                    work_dir=work_dir,
                    task_query=task_query,
                    df_labor=df_labor,
                    task_id_list=task_id_list,
                    ignored_task_id_list=ignored_task_id_list,
                    user_id_list=user_id_list,
                    update=update,
                    download_latest=download_latest,
                    is_get_task_histories_one_of_each=is_get_task_histories_one_of_each,
                    start_date=start_date,
                    end_date=end_date,
                    minimal_output=minimal_output,
                    is_get_labor=is_get_labor,
                )
                if output_project_dir is not None:
                    output_project_dir_list.append(output_project_dir)

        return output_project_dir_list

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

        ignored_task_id_list = (
            annofabcli.common.cli.get_list_from_args(args.ignored_task_id) if args.ignored_task_id is not None else None
        )
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None

        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id) if args.user_id is not None else None
        project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)

        if args.work_dir is not None:
            work_dir = args.work_dir
        else:
            work_dir = annofabcli.utils.get_cache_dir()

        root_output_dir: Path = args.output_dir

        if args.get_labor:
            logger.warning(f"'--get_labor'は非推奨です。将来的にこのオプションは廃止されます。替わりに '--labor_csv' をご利用ください。")

        if args.labor_csv is None and not args.get_labor:
            logger.warning(f"'--get_labor'が指定されていないので、実績作業時間に関する情報は出力されません。")

        df_labor = pandas.read_csv(args.labor_csv) if args.labor_csv is not None else None

        if len(project_id_list) == 1:
            visualize_statistics(
                annofab_service=self.service,
                annofab_facade=self.facade,
                project_id=project_id_list[0],
                output_project_dir=root_output_dir,
                work_dir=work_dir,
                task_query=task_query,
                df_labor=df_labor,
                task_id_list=task_id_list,
                ignored_task_id_list=ignored_task_id_list,
                user_id_list=user_id_list,
                update=not args.not_update,
                download_latest=args.latest,
                is_get_task_histories_one_of_each=args.get_task_histories_one_of_each,
                start_date=args.start_date,
                end_date=args.end_date,
                is_get_labor=args.get_labor,
                minimal_output=args.minimal,
            )

            if args.merge:
                logger.warning(f"出力した統計情報は1件以下なので、`merge`ディレクトリを出力しません。")

        else:
            # project_idが複数指定された場合は、project_titleのディレクトリに統計情報を出力する
            output_project_dir_list = self.visualize_statistics_for_project_list(
                root_output_dir=root_output_dir,
                project_id_list=project_id_list,
                work_dir=work_dir,
                task_query=task_query,
                df_labor=df_labor,
                task_id_list=task_id_list,
                ignored_task_id_list=ignored_task_id_list,
                user_id_list=user_id_list,
                update=not args.not_update,
                download_latest=args.latest,
                is_get_task_histories_one_of_each=args.get_task_histories_one_of_each,
                start_date=args.start_date,
                end_date=args.end_date,
                minimal_output=args.minimal,
                is_get_labor=args.get_labor,
                parallelism=args.parallelism,
            )

            if args.merge:
                merge_visualization_dir(
                    project_dir_list=output_project_dir_list,
                    output_dir=root_output_dir / "merge",
                    user_id_list=user_id_list,
                    minimal_output=args.minimal,
                )

            if len(output_project_dir_list) > 0:
                write_project_performance_csv(output_project_dir_list, root_output_dir / "プロジェクトごとの生産性と品質.csv")
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
            " ``file://`` を先頭に付けると、project_idが記載されたファイルを指定できます。"
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
            " ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="タスクの検索クエリをJSON形式で指定します。指定しない場合はすべてのタスクを取得します。\n"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        "クエリのキーは、task_id, phase, phase_stage, status のみです。",
    )

    parser.add_argument(
        "-t",
        "--task_id",
        type=str,
        required=False,
        nargs="+",
        help="集計対象のタスクのtask_idを指定します。\n" + " ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--start_date", type=str, help="指定した日付（'YYYY-MM-DD'）以降に教師付を開始したタスクを集計する。")
    parser.add_argument("--end_date", type=str, help="指定した日付（'YYYY-MM-DD'）以前に更新されたタスクを集計する。")

    parser.add_argument(
        "--ignored_task_id",
        nargs="+",
        help=("集計対象外のタスクのtask_idを指定します。 ``--task_id`` より優先度が高いです。\n" " ``file://`` を先頭に付けると、一覧が記載されたファイルを指定できます。"),
    )

    parser.add_argument(
        "--not_update",
        action="store_true",
        help="作業ディレクトリ内のファイルを参照して、統計情報を出力します。" "AnnoFab Web APIへのアクセスを最小限にします。",
    )

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
        "--work_dir",
        type=Path,
        help="作業ディレクトリのパス。指定しない場合はannofabcliのキャッシュディレクトリ（'$HOME/.cache/annofabcli'）に保存します。",
    )

    parser.add_argument(
        "--labor_csv",
        type=Path,
        help=(
            "実績作業時間情報が格納されたCSVを指定してください。指定しない場合は、実績作業時間は0とみなします。列名は以下の通りです。\n"
            " * date\n"
            " * account_id\n"
            " * project_id\n"
            " * actual_worktime_hour\n"
        ),
    )

    parser.add_argument(
        "--get_labor",
        action="store_true",
        help=(
            "[DEPRECATED] labor関係のWebAPIを使って実績作業時間情報を取得します。\n"
            "将来的にlabor関係のWebAPIは利用できなくなります。替わりに ``--labor_csv`` を利用してください。\n"
        ),
    )

    parser.add_argument(
        "--minimal",
        action="store_true",
        help="必要最小限のファイルを出力します。",
    )

    parser.add_argument(
        "--merge",
        action="store_true",
        help="指定した場合、複数のproject_idを指定したときに、マージした統計情報も出力します。ディレクトリ名は ``merge`` です。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        help="並列度。 ``--project_id`` に複数のproject_idを指定したときのみ有効なオプションです。指定しない場合は、逐次的に処理します。また、必ず ``--yes`` を指定してください。",
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
