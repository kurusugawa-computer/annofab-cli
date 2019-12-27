import argparse
import json
import logging.handlers
from pathlib import Path
from typing import Any, Dict, List

import annofabapi
from annofabapi.models import ProjectMemberRole, TaskPhase

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.statistics.database import Database
from annofabcli.statistics.graph import Graph
from annofabcli.statistics.table import AggregationBy, Table
from annofabcli.statistics.tsv import Tsv

logger = logging.getLogger(__name__)


def write_project_name_file(annofab_service: annofabapi.Resource, project_id: str, output_project_dir: Path):
    """
    ファイル名がプロジェクト名のjsonファイルを生成する。
    """
    project_info = annofab_service.api.get_project(project_id)[0]
    project_title = project_info["title"]
    logger.info(f"project_titile = {project_title}")
    filename = annofabcli.utils.to_filename(project_title)
    output_project_dir.mkdir(exist_ok=True, parents=True)
    with open(str(output_project_dir / f"{filename}.json"), "w") as f:
        json.dump(project_info, f, ensure_ascii=False, indent=2)


class VisualizeStatistics(AbstractCommandLineInterface):
    """
    統計情報を可視化する。
    """

    def visualize_statistics(
        self,
        project_id: str,
        work_dir: Path,
        output_dir: Path,
        task_query: Dict[str, Any],
        ignored_task_id_list: List[str],
        user_id_list: List[str],
        update: bool = False,
        should_update_annotation_zip: bool = False,
        should_update_task_json: bool = False,
    ):
        """
        タスク一覧を出力する

        Args:
            project_id: 対象のproject_id
            task_query: タスク検索クエリ

        """

        super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER])

        checkpoint_dir = work_dir / project_id
        checkpoint_dir.mkdir(exist_ok=True, parents=True)

        database = Database(self.service, project_id, str(checkpoint_dir))
        if update:
            database.update_db(
                task_query,
                ignored_task_id_list,
                should_update_annotation_zip=should_update_annotation_zip,
                should_update_task_json=should_update_task_json,
            )

        table_obj = Table(database, task_query, ignored_task_id_list)
        write_project_name_file(self.service, project_id, output_dir)
        tsv_obj = Tsv(str(output_dir), project_id)
        graph_obj = Graph(str(output_dir), project_id)

        task_df = table_obj.create_task_df()
        task_history_df = table_obj.create_task_history_df()
        inspection_df = table_obj.create_inspection_df()
        inspection_df_all = table_obj.create_inspection_df(only_error_corrected=False)

        member_df = table_obj.create_member_df(task_df)
        annotation_df = table_obj.create_task_for_annotation_df()
        by_date_df = table_obj.create_dataframe_by_date(task_df)
        task_cumulative_df_by_annotator = table_obj.create_cumulative_df_by_first_annotator(task_df)
        task_cumulative_df_by_inspector = table_obj.create_cumulative_df_by_first_inspector(task_df)
        task_cumulative_df_by_acceptor = table_obj.create_cumulative_df_by_first_acceptor(task_df)

        try:
            tsv_obj.write_task_list(task_df, dropped_columns=["histories_by_phase", "input_data_id_list"])
            tsv_obj.write_task_history_list(task_history_df)
            tsv_obj.write_inspection_list(df=inspection_df, dropped_columns=["data"], only_error_corrected=True)
            tsv_obj.write_inspection_list(
                df=inspection_df_all, dropped_columns=["data"], only_error_corrected=False,
            )

            tsv_obj.write_member_list(member_df)
            tsv_obj.write_ラベルごとのアノテーション数(annotation_df)

            tsv_obj.write_教師付作業者別日毎の情報(by_date_df)
            tsv_obj.write_ユーザ別日毎の作業時間(table_obj.create_account_statistics_df())

            for phase in TaskPhase:
                df_by_inputs = table_obj.create_worktime_per_image_df(AggregationBy.BY_INPUTS, phase)
                tsv_obj.write_メンバー別作業時間平均_画像1枚あたり(df_by_inputs, phase)
                df_by_tasks = table_obj.create_worktime_per_image_df(AggregationBy.BY_TASKS, phase)
                tsv_obj.write_メンバー別作業時間平均_タスク1個あたり(df_by_tasks, phase)

        except Exception as e:  # pylint: disable=broad-except
            logger.warning(e)
            logger.exception(e)

        try:
            graph_obj.write_histogram_for_annotation_count_by_label(annotation_df)
            graph_obj.write_histogram_for_worktime(task_df)
            graph_obj.write_histogram_for_other(task_df)
            graph_obj.write_cumulative_line_graph_for_annotator(
                df=task_cumulative_df_by_annotator, first_annotation_user_id_list=user_id_list,
            )

            graph_obj.write_cumulative_line_graph_for_inspector(
                df=task_cumulative_df_by_inspector, first_inspection_user_id_list=user_id_list,
            )

            graph_obj.write_cumulative_line_graph_for_acceptor(
                df=task_cumulative_df_by_acceptor, first_acceptance_user_id_list=user_id_list,
            )

            graph_obj.write_productivity_line_graph_for_annotator(
                df=by_date_df, first_annotation_user_id_list=user_id_list
            )

        except Exception as e:  # pylint: disable=broad-except
            logger.warning(e)
            logger.exception(e)

    def main(self):
        args = self.args
        task_query = annofabcli.common.cli.get_json_from_args(args.task_query)
        ignored_task_id_list = annofabcli.common.cli.get_list_from_args(args.ignored_task_id)
        user_id_list = annofabcli.common.cli.get_list_from_args(args.user_id)

        self.visualize_statistics(
            args.project_id,
            output_dir=Path(args.output_dir),
            work_dir=Path(args.work_dir),
            task_query=task_query,
            ignored_task_id_list=ignored_task_id_list,
            user_id_list=user_id_list,
            update=not args.not_update,
            should_update_annotation_zip=args.update_annotation,
            should_update_task_json=args.update_task_json,
        )


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    VisualizeStatistics(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力ディレクトリのパス")

    parser.add_argument(
        "-u",
        "--user_id",
        nargs="+",
        help=(
            "メンバごとの統計グラフに表示するユーザのuser_idを指定してください。"
            "指定しない場合は、辞書順に並べた上位20人が表示されます。"
            "file://`を先頭に付けると、一覧が記載されたファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="タスクの検索クエリをJSON形式で指定します。指定しない場合はすべてのタスクを取得します。"
        "`file://`を先頭に付けると、JSON形式のファイルを指定できます。"
        "クエリのキーは、phase, statusのみです。[getTasks API](https://annofab.com/docs/api/#operation/getTasks) 参照",
    )

    parser.add_argument(
        "--ignored_task_id",
        nargs="+",
        help=("可視化対象外のタスクのtask_id。" "指定しない場合は、すべてのタスクが可視化対象です。" "file://`を先頭に付けると、一覧が記載されたファイルを指定できます。"),
    )

    parser.add_argument(
        "--not_update", action="store_true", help="作業ディレクトリ内のファイルを参照して、統計情報を出力します。" "AnnoFab Web APIへのアクセスを最小限にします。",
    )

    parser.add_argument(
        "--update_annotation",
        action="store_true",
        help="アノテーションzipを更新してから、アノテーションzipをダウンロードします。" "ただし、アノテーションzipの最終更新日時がタスクの最終更新日時より新しい場合は、アノテーションzipを更新しません。",
    )

    parser.add_argument(
        "--update_task_json", action="store_true", help="タスク全件ファイルJSONを更新してから、タスク全件ファイルJSONをダウンロードします。",
    )

    parser.add_argument(
        "--work_dir", type=str, default=".annofab-cli", help="作業ディレクトリのパス。指定しない場合カレントの'.annofab-cli'ディレクトリに保存する",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "visualize"
    subcommand_help = "統計情報を可視化したファイルを出力します。"
    description = "統計情報を可視化したファイルを出力します。毎日 03:00JST頃に更新されます。"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog)
    parse_args(parser)
