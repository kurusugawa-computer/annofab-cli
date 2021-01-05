import argparse
import logging
from typing import Callable, Optional

from annofabapi.models import Inspection

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import ArgumentParser, FormatArgument, build_annofabapi_resource_and_login
from annofabcli.inspection_comment.list_inspections import PrintInspections

logger = logging.getLogger(__name__)


def create_filter_func(
    commenter_user_id: Optional[str],
    inspection_comment: Optional[str],
    phase: Optional[str],
    phase_stage: Optional[int],
) -> Callable[[Inspection], bool]:
    def filter_inspection(arg_inspection: Inspection) -> bool:  # pylint: disable=too-many-return-statements

        # 未処置コメントのみ、変更する
        if arg_inspection["status"] != "annotator_action_required":
            return False

        # 返信コメントを除く
        if arg_inspection["parent_inspection_id"] is not None:
            return False

        if commenter_user_id is not None:
            if arg_inspection["commenter_user_id"] != commenter_user_id:
                return False

        if inspection_comment is not None:
            if arg_inspection["comment"] != inspection_comment:
                return False

        if phase is not None:
            if arg_inspection["phase"] != phase:
                return False

        if phase_stage is not None:
            if arg_inspection["phase_stage"] != phase_stage:
                return False

        return True

    return filter_inspection


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id(
        required=True,
        help_message="対象のタスクのtask_idを指定します。　" "`file://`を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--inspection_comment", type=str, help="「検査コメントの中身」で絞り込みます。指定しない場合は絞り込みません。")

    parser.add_argument("--commenter_user_id", type=str, help="「検査コメントを付与したユーザのuser_id」で絞り込みます。指定しない場合は絞り込みません。")

    parser.add_argument("--phase", type=str, help="「検査コメントを付与したときのタスクフェーズ」で絞り込みます。指定しない場合は絞り込みません。")

    parser.add_argument("--phase_stage", type=int, help="「検査コメントを付与したときのタスクフェーズのステージ番号」で絞り込みます。指定しない場合は絞り込みません。")

    argument_parser.add_format(
        choices=[
            FormatArgument.CSV,
            FormatArgument.JSON,
            FormatArgument.PRETTY_JSON,
            FormatArgument.INSPECTION_ID_LIST,
        ],
        default=FormatArgument.CSV,
    )
    argument_parser.add_output()
    argument_parser.add_csv_format()
    argument_parser.add_query()

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)

    task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)

    filter_inspection = create_filter_func(
        args.commenter_user_id, args.inspection_comment, phase=args.phase, phase_stage=args.phase_stage
    )

    PrintInspections(service, facade, args).print_inspections(
        project_id=args.project_id,
        task_id_list=task_id_list,
        filter_inspection=filter_inspection,
    )


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_unprocessed"

    subcommand_help = "未処置の検査コメント一覧を出力します(廃止予定)"

    description = "未処置の検査コメント一覧を出力します(廃止予定)"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
