from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from annofabapi.models import CommentType, ProjectMemberRole

import annofabcli.common.cli
from annofabcli.comment.put_comment import (
    PutCommentMain,
    convert_cli_inspection_comment_list,
    read_inspection_comment_csv,
)
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class CreateInspectionComment(CommandLine):
    COMMON_MESSAGE = "annofabcli comment create_inspection: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、'--yes' を指定してください。",
                file=sys.stderr,
            )
            return False

        if args.csv is not None and not args.csv.exists():
            print(f"{self.COMMON_MESSAGE} argument --csv: ファイルパスが存在しません。 :: {args.csv}", file=sys.stderr)  # noqa: T201
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        required_project_member_roles = [ProjectMemberRole.OWNER] if args.cancel_acceptance else [ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER]
        super().validate_project(args.project_id, required_project_member_roles)

        if args.json is not None:
            comment_list: Any = annofabcli.common.cli.get_json_from_args(args.json)
            if not isinstance(comment_list, list):
                print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。配列を指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
            comments_for_task_list = convert_cli_inspection_comment_list(comment_list)
        elif args.csv is not None:
            try:
                comments_for_task_list = read_inspection_comment_csv(args.csv)
            except ValueError as e:
                print(f"{self.COMMON_MESSAGE} argument --csv: CSVの読み込みに失敗しました。 :: {e}", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        else:
            print(f"{self.COMMON_MESSAGE} --json または --csv のいずれかを指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = PutCommentMain(self.service, project_id=args.project_id, comment_type=CommentType.INSPECTION, all_yes=self.all_yes)
        main_obj.add_comments_for_task_list(
            comments_for_task_list=comments_for_task_list,
            parallelism=args.parallelism,
            put_mode="create",
            cancel_acceptance=args.cancel_acceptance,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CreateInspectionComment(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    input_group = parser.add_mutually_exclusive_group(required=True)

    sample_json = [
        {
            "task_id": "task1",
            "input_data_id": "input_data1",
            "comment": "type属性が間違っています。",
            "data": {"x": 10, "y": 20, "_type": "Point"},
        }
    ]
    input_group.add_argument(
        "--json",
        type=str,
        help=(
            f"作成する検査コメントの内容をJSON形式で指定してください。``file://`` を先頭に付けると、JSON形式のファイルを指定できます。\n\n"
            f"各コメントには ``comment_id`` を指定することができます。省略した場合は自動的にUUIDv4が生成されます。\n\n"
            f"(ex)  ``{json.dumps(sample_json, ensure_ascii=False)}``"
        ),
    )

    input_group.add_argument(
        "--csv",
        type=Path,
        help=(
            "作成する検査コメントの内容をCSV形式で指定してください。\n"
            "CSVには以下の列が必要です：\n\n"
            " * ``task_id`` （必須）: タスクID\n"
            " * ``input_data_id`` （必須）: 入力データID\n"
            " * ``comment`` （必須）: コメント本文\n"
            ' * ``data`` （任意）: コメント位置情報（JSON形式の文字列。例: ``\'{"x":10,"y":20,"_type":"Point"}\' `` ）\n'
            " * ``annotation_id`` （任意）: 紐付けるアノテーションID\n"
            ' * ``phrases`` （任意）: 定型指摘IDのリスト（JSON配列形式の文字列。例: ``\'["ID1","ID2"]\' `` ）\n'
            " * ``comment_id`` （任意）: コメントID（省略時はUUIDv4自動生成）\n"
        ),
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.add_argument(
        "--cancel_acceptance",
        action="store_true",
        help="完了状態の受入フェーズを取り消してから検査コメントを作成します。差し戻し前に検査コメントを作成する場合などに使用します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "create_inspection"
    subcommand_help = "検査コメントを作成します"
    description = "検査コメントを作成します。comment_idがすでに存在する場合、デフォルトではスキップします。"
    epilog = "チェッカーロールまたはオーナロールを持つユーザで実行してください。``--cancel_acceptance`` を指定した場合は、オーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
