from __future__ import annotations

import argparse
import functools
import logging.handlers
import re
import sys
import tempfile
from multiprocessing import Pool
from pathlib import Path
from typing import Any, Callable, List, Optional

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
from annofabcli.statistics.visualization.dataframe.actual_worktime import ActualWorktime
from annofabcli.statistics.visualization.dataframe.annotation_count import AnnotationCount
from annofabcli.statistics.visualization.dataframe.cumulative_productivity import (
    AcceptorCumulativeProductivity,
    AnnotatorCumulativeProductivity,
    InspectorCumulativeProductivity,
)
from annofabcli.statistics.visualization.dataframe.inspection_comment_count import InspectionCommentCount
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
from annofabcli.statistics.visualization.dataframe.task_history import TaskHistory
from annofabcli.statistics.visualization.dataframe.task_worktime_by_phase_user import TaskWorktimeByPhaseUser
from annofabcli.statistics.visualization.dataframe.user import User
from annofabcli.statistics.visualization.dataframe.user_performance import UserPerformance
from annofabcli.statistics.visualization.dataframe.whole_performance import WholePerformance
from annofabcli.statistics.visualization.dataframe.whole_productivity_per_date import (
    WholeProductivityPerCompletedDate,
    WholeProductivityPerFirstAnnotationStartedDate,
)
from annofabcli.statistics.visualization.dataframe.worktime_per_date import WorktimePerDate
from annofabcli.statistics.visualization.filtering_query import FilteringQuery, filter_tasks
from annofabcli.statistics.visualization.model import WorktimeColumn
from annofabcli.statistics.visualization.project_dir import ProjectDir, ProjectInfo
from annofabcli.statistics.visualization.visualization_source_files import VisualizationSourceFiles

logger = logging.getLogger(__name__)


def get_project_output_dir(project_title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "__", project_title)


class WriteCsvGraph:
    def __init__(
        self,
        service: annofabapi.Resource,
        project_id: str,
        filtering_query: FilteringQuery,
        visualization_source_files: VisualizationSourceFiles,
        output_dir: Path,
        actual_worktime: ActualWorktime,
        *,
        annotation_count: Optional[AnnotationCount] = None,
        minimal_output: bool = False,
        output_only_text: bool = False,
    ) -> None:
        self.service = service
        self.project_id = project_id
        self.output_dir = output_dir
        self.filtering_query = filtering_query
        self.visualize_source_files = visualization_source_files
        self.actual_worktime = actual_worktime
        self.minimal_output = minimal_output
        self.output_only_text = output_only_text
        self.annotation_count = annotation_count

        self.project_dir = ProjectDir(output_dir)

        self.task: Optional[Task] = None
        self.worktime_per_date: Optional[WorktimePerDate] = None

    def _catch_exception(self, function: Callable[..., Any]) -> Callable[..., Any]:
        """
        Exceptionをキャッチしてログにstacktraceを出力する。
        """

        def wrapped(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except Exception:  # pylint: disable=broad-except
                logger.warning(f"project_id='{self.project_id}'であるプロジェクトでのファイル出力に失敗しました。", exc_info=True)
                return None

        return wrapped

    def _get_task(self) -> Task:
        if self.task is None:
            if self.annotation_count is None:
                # アノテーションZIPからアノテーション数を取得
                annotation_count = AnnotationCount.from_annotation_zip(self.visualize_source_files.annotation_zip_path, project_id=self.project_id)
            else:
                annotation_count = self.annotation_count

            inspection_comment_count = InspectionCommentCount.from_api_content(self.visualize_source_files.read_comments_json())

            tasks = self.visualize_source_files.read_tasks_json()
            task_histories = self.visualize_source_files.read_task_histories_json()
            new_tasks = filter_tasks(tasks, self.filtering_query, task_histories=task_histories)
            logger.debug(f"project_id='{self.project_id}' :: 集計対象タスクは {len(new_tasks)} / {len(tasks)} 件です。")

            self.task = Task.from_api_content(
                tasks=new_tasks,
                task_histories=task_histories,
                inspection_comment_count=inspection_comment_count,
                annotation_count=annotation_count,
                project_id=self.project_id,
                annofab_service=self.service,
            )

        return self.task

    def _get_worktime_per_date(self) -> WorktimePerDate:
        if self.worktime_per_date is None:
            self.worktime_per_date = WorktimePerDate.from_webapi(
                self.service,
                self.project_id,
                actual_worktime=self.actual_worktime,
                task_history_event_json=self.visualize_source_files.task_history_event_json_path,
                start_date=self.filtering_query.start_date,
                end_date=self.filtering_query.end_date,
            )
        return self.worktime_per_date

    def write_task_info(self) -> None:
        """
        タスクに関するヒストグラムを出力する。

        """
        obj = self._get_task()

        self.project_dir.write_task_list(obj)

        if not self.output_only_text:
            self.project_dir.write_task_histogram(obj)

    def write_user_performance(self) -> None:
        """
        ユーザごとの生産性と品質に関する情報を出力する。
        """
        task_history = TaskHistory.from_api_content(self.visualize_source_files.read_task_histories_json())

        project_members = self.service.wrapper.get_all_project_members(self.project_id, query_params={"include_inactive_member": True})
        user = User(pandas.DataFrame(project_members))

        # タスク、フェーズ、ユーザごとの作業時間を出力する
        task_worktime_obj = TaskWorktimeByPhaseUser.from_df_wrapper(
            task_history=task_history,
            user=user,
            task=self._get_task(),
            project_id=self.project_id,
        )
        self.project_dir.write_task_worktime_list(task_worktime_obj)

        user_performance = UserPerformance.from_df_wrapper(
            task_worktime_by_phase_user=task_worktime_obj,
            worktime_per_date=self._get_worktime_per_date(),
        )

        self.project_dir.write_user_performance(user_performance)

        whole_performance = WholePerformance.from_df_wrapper(
            task_worktime_by_phase_user=task_worktime_obj,
            worktime_per_date=self._get_worktime_per_date(),
        )
        self.project_dir.write_whole_performance(whole_performance)

        if not self.output_only_text:
            self.project_dir.write_user_performance_scatter_plot(user_performance)

    def write_cumulative_linegraph_by_user(self, user_id_list: Optional[List[str]] = None) -> None:
        """ユーザごとの累積折れ線グラフをプロットする。"""
        df_task = self._get_task().df

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
        worktime_per_date_obj = self._get_worktime_per_date()

        self.project_dir.write_worktime_per_date_user(worktime_per_date_obj)

        task = self._get_task()
        productivity_per_completed_date_obj = WholeProductivityPerCompletedDate.from_df_wrapper(task, worktime_per_date_obj)

        self.project_dir.write_whole_productivity_per_date(productivity_per_completed_date_obj)

        productivity_per_started_date_obj = WholeProductivityPerFirstAnnotationStartedDate.from_task(task)
        self.project_dir.write_whole_productivity_per_first_annotation_started_date(productivity_per_started_date_obj)

        if not self.output_only_text:
            self.project_dir.write_worktime_line_graph(worktime_per_date_obj, user_id_list=user_id_list)
            self.project_dir.write_whole_productivity_line_graph_per_date(productivity_per_completed_date_obj)
            self.project_dir.write_whole_productivity_line_graph_per_annotation_started_date(productivity_per_started_date_obj)

    def write_user_productivity_per_date(self, user_id_list: Optional[List[str]] = None) -> None:
        """ユーザごとの日ごとの生産性情報を出力する。"""
        task = self._get_task()

        annotator_per_date_obj = AnnotatorProductivityPerDate.from_df_task(task.df)
        inspector_per_date_obj = InspectorProductivityPerDate.from_df_task(task.df)
        acceptor_per_date_obj = AcceptorProductivityPerDate.from_df_task(task.df)

        # 開始日ごとのCSVを出力
        self.project_dir.write_performance_per_started_date_csv(annotator_per_date_obj, phase=TaskPhase.ANNOTATION)
        self.project_dir.write_performance_per_started_date_csv(inspector_per_date_obj, phase=TaskPhase.INSPECTION)
        self.project_dir.write_performance_per_started_date_csv(acceptor_per_date_obj, phase=TaskPhase.ACCEPTANCE)

        if not self.output_only_text:
            self.project_dir.write_performance_line_graph_per_date(annotator_per_date_obj, phase=TaskPhase.ANNOTATION, user_id_list=user_id_list)
            self.project_dir.write_performance_line_graph_per_date(inspector_per_date_obj, phase=TaskPhase.INSPECTION, user_id_list=user_id_list)
            self.project_dir.write_performance_line_graph_per_date(acceptor_per_date_obj, phase=TaskPhase.ACCEPTANCE, user_id_list=user_id_list)


class VisualizingStatisticsMain:
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        temp_dir: Path,
        # タスクの絞り込み関係
        task_query: Optional[TaskQuery],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        # 出力方法
        minimal_output: bool = False,
        output_only_text: bool = False,
        # その他
        download_latest: bool = False,
        is_get_task_histories_one_of_each: bool = False,
        actual_worktime: Optional[ActualWorktime] = None,
        annotation_count: Optional[AnnotationCount] = None,
        user_ids: Optional[List[str]] = None,
        not_download_visualization_source_files: bool = False,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.temp_dir = temp_dir

        self.filtering_query = FilteringQuery(task_query=task_query, start_date=start_date, end_date=end_date)
        self.minimal_output = minimal_output
        self.output_only_text = output_only_text
        self.download_latest = download_latest
        self.is_get_task_histories_one_of_each = is_get_task_histories_one_of_each
        self.actual_worktime = actual_worktime
        self.annotation_count = annotation_count
        self.user_ids = user_ids
        self.not_download_visualization_source_files = not_download_visualization_source_files

    def write_project_info_json(self, project_id: str, project_dir: ProjectDir) -> None:
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
            query=self.filtering_query,
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

        self.facade.validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        project_dir = ProjectDir(output_project_dir)
        self.write_project_info_json(project_id=project_id, project_dir=project_dir)

        if self.actual_worktime is not None:
            df_actual_worktime = self.actual_worktime.df
            df_actual_worktime = df_actual_worktime[df_actual_worktime["project_id"] == project_id]

            if self.filtering_query.start_date is not None:
                df_actual_worktime = df_actual_worktime[df_actual_worktime["date"] >= self.filtering_query.start_date]
            if self.filtering_query.end_date is not None:
                df_actual_worktime = df_actual_worktime[df_actual_worktime["date"] <= self.filtering_query.end_date]

        else:
            df_actual_worktime = ActualWorktime.empty()

        if self.annotation_count is not None:
            # project_idで絞り込む
            df_annotation_count = self.annotation_count.df
            df_annotation_count = df_annotation_count[df_annotation_count["project_id"] == project_id]
            # `annotation_count = None`にする理由：後続の処理でアノテーションZIPからアノテーション数を算出するようにするため
            if len(df_annotation_count) == 0:
                annotation_count = None
            else:
                annotation_count = AnnotationCount(df_annotation_count)
        else:
            annotation_count = None

        visualization_source_files = VisualizationSourceFiles(
            self.service,
            project_id,
            self.temp_dir,
        )
        if not self.not_download_visualization_source_files:
            visualization_source_files.write_files(
                is_latest=self.download_latest, should_get_task_histories_one_of_each=self.is_get_task_histories_one_of_each
            )

        write_obj = WriteCsvGraph(
            self.service,
            project_id,
            filtering_query=self.filtering_query,
            visualization_source_files=visualization_source_files,
            output_dir=output_project_dir,
            actual_worktime=ActualWorktime(df_actual_worktime),
            annotation_count=annotation_count,
            minimal_output=self.minimal_output,
            output_only_text=self.output_only_text,
        )

        write_obj._catch_exception(write_obj.write_user_performance)()
        write_obj._catch_exception(write_obj.write_worktime_per_date)(self.user_ids)

        write_obj._catch_exception(write_obj.write_task_info)()

        # 折れ線グラフ
        write_obj.write_cumulative_linegraph_by_user(self.user_ids)

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

        if args.not_download:
            if args.temp_dir is None:
                print(
                    f"{COMMON_MESSAGE} argument --not_download: '--not_download'を指定する場合は'--temp_dir'も指定してください。",
                    file=sys.stderr,
                )
                return False

        return True

    def visualize_statistics(
        self,
        temp_dir: Path,
        task_query: Optional[TaskQuery],
        user_id_list: Optional[list[str]],
        actual_worktime: ActualWorktime,
        annotation_count: Optional[AnnotationCount],
        download_latest: bool,
        is_get_task_histories_one_of_each: bool,
        start_date: Optional[str],
        end_date: Optional[str],
        minimal_output: bool,
        output_only_text: bool,
        not_download_visualization_source_files: bool,
        project_id_list: list[str],
        root_output_dir: Path,
        parallelism: Optional[int],
    ):
        main_obj = VisualizingStatisticsMain(
            service=self.service,
            temp_dir=temp_dir,
            task_query=task_query,
            user_ids=user_id_list,
            actual_worktime=actual_worktime,
            annotation_count=annotation_count,
            download_latest=download_latest,
            is_get_task_histories_one_of_each=is_get_task_histories_one_of_each,
            start_date=start_date,
            end_date=end_date,
            minimal_output=minimal_output,
            output_only_text=output_only_text,
            not_download_visualization_source_files=not_download_visualization_source_files,
        )

        if len(project_id_list) == 1:
            main_obj.visualize_statistics(project_id_list[0], root_output_dir)

        else:
            # project_idが複数指定された場合は、project_titleのディレクトリに統計情報を出力する
            output_project_dir_list = main_obj.visualize_statistics_for_project_list(
                project_id_list=project_id_list,
                root_output_dir=root_output_dir,
                parallelism=parallelism,
            )

            if len(output_project_dir_list) > 0:
                project_dir_list = [ProjectDir(e) for e in output_project_dir_list]
                project_performance = ProjectPerformance.from_project_dirs(project_dir_list)
                project_performance.to_csv(root_output_dir / "プロジェクトごとの生産性と品質.csv")

                project_actual_worktime = ProjectWorktimePerMonth.from_project_dirs(project_dir_list, WorktimeColumn.ACTUAL_WORKTIME_HOUR)
                project_actual_worktime.to_csv(root_output_dir / "プロジェクごとの毎月の実績作業時間.csv")

                project_monitored_worktime = ProjectWorktimePerMonth.from_project_dirs(project_dir_list, WorktimeColumn.MONITORED_WORKTIME_HOUR)
                project_monitored_worktime.to_csv(root_output_dir / "プロジェクごとの毎月の計測作業時間.csv")

            else:
                logger.warning("出力した統計情報は0件なので、`プロジェクトごとの生産性と品質.csv`を出力しません。")

    def main(self) -> None:  # pylint: disable=too-many-branches
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        dict_task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        task_query: Optional[TaskQuery] = TaskQuery.from_dict(dict_task_query) if dict_task_query is not None else None

        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id) if args.user_id is not None else None
        project_id_list = annofabcli.common.cli.get_list_from_args(args.project_id)

        root_output_dir: Path = args.output_dir

        if args.labor_csv is None:
            logger.warning("'--labor_csv'が指定されていないので、実績作業時間に関する情報は出力されません。")
            actual_worktime = ActualWorktime.empty()
        else:
            df_actual_worktime = pandas.read_csv(args.labor_csv)
            if not ActualWorktime.required_columns_exist(df_actual_worktime):
                logger.error(
                    "引数`--labor_csv`のCSVには以下の列が存在しないので、終了します。\n`project_id`, `date`, `account_id`, `actual_worktime_hour`"
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            actual_worktime = ActualWorktime(df_actual_worktime)

        if args.annotation_count_csv is not None:
            df_annotation_count = pandas.read_csv(args.annotation_count_csv)
            if not AnnotationCount.required_columns_exist(df_annotation_count):
                logger.error(
                    "引数`--annotation_count_csv`のCSVには以下の列が存在しないので、終了します。\n`project_id`, `task_id`, `annotation_count`"
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            annotation_count = AnnotationCount(df_annotation_count)
        else:
            annotation_count = None

        if args.temp_dir is None:
            with tempfile.TemporaryDirectory() as str_temp_dir:
                self.visualize_statistics(
                    temp_dir=Path(str_temp_dir),
                    task_query=task_query,
                    user_id_list=user_id_list,
                    actual_worktime=actual_worktime,
                    annotation_count=annotation_count,
                    download_latest=args.latest,
                    is_get_task_histories_one_of_each=args.get_task_histories_one_of_each,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    minimal_output=args.minimal,
                    output_only_text=args.output_only_text,
                    project_id_list=project_id_list,
                    root_output_dir=root_output_dir,
                    parallelism=args.parallelism,
                    # `tempfile.TemporaryDirectory`で作成したディレクトリを利用する場合は、必ずダウンロードが必要なの`False`を指定する
                    not_download_visualization_source_files=False,
                )
        else:
            self.visualize_statistics(
                temp_dir=args.temp_dir,
                task_query=task_query,
                user_id_list=user_id_list,
                actual_worktime=actual_worktime,
                annotation_count=annotation_count,
                download_latest=args.latest,
                is_get_task_histories_one_of_each=args.get_task_histories_one_of_each,
                start_date=args.start_date,
                end_date=args.end_date,
                minimal_output=args.minimal,
                output_only_text=args.output_only_text,
                project_id_list=project_id_list,
                root_output_dir=root_output_dir,
                parallelism=args.parallelism,
                not_download_visualization_source_files=args.not_download,
            )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeStatistics(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
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

    parser.add_argument("--start_date", type=str, help="指定した日付（ ``YYYY-MM-DD`` ）以降に教師付を開始したタスクから生産性を算出します。")
    parser.add_argument("--end_date", type=str, help="指定した日付（ ``YYYY-MM-DD`` ）以前に教師付を開始したタスクから生産性を算出します。")

    parser.add_argument(
        "--latest",
        action="store_true",
        help="統計情報の元になるファイル（アノテーションzipなど）の最新版を参照します。このオプションを指定すると、各ファイルを更新するのに5分以上待ちます。\n"
        "ただしWebAPIの都合上、'タスク履歴全件ファイル'は最新版を参照できません。タスク履歴の最新版を参照する場合は ``--get_task_histories_one_of_each`` を指定してください。",  # noqa: E501
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
            "* project_id \n"
        ),
    )

    parser.add_argument(
        "--annotation_count_csv",
        type=Path,
        help=(
            "指定されたCSVに記載されているアノテーション数を参照して、生産量や生産性を算出します。未指定の場合はアノテーションZIPからアノテーション数をカウントします。CSVには以下の列が必要です。\n"
            "\n"
            "* project_id\n"
            "* task_id\n"
            "* annotation_count\n"
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
        "--temp_dir",
        type=Path,
        help=("指定したディレクトリに、アノテーションZIPなど可視化に必要なファイルを出力します。"),
    )

    parser.add_argument(
        "--not_download",
        action="store_true",
        help=(
            "指定した場合、アノテーションZIPなどのファイルをダウンロードせずに、`--temp_dir`で指定したディレクトリ内のファイルを読み込みます。`--temp_dir`は必須です。"
        ),
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        help="並列度。 ``--project_id`` に複数のproject_idを指定したときのみ有効なオプションです。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "visualize"
    subcommand_help = "生産性に関するCSVファイルやグラフを出力します。"
    description = "生産性に関するCSVファイルやグラフを出力します。"
    epilog = "アノテーションユーザまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
