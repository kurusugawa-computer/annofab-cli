from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from annofabapi.models import CommentType

import annofabcli.common.cli
from annofabcli.comment.put_comment import PutCommentMain, convert_cli_comments, read_comment_csv
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class PutInspectionComment(CommandLine):
    COMMON_MESSAGE = "annofabcli comment put_onhold: error:"

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

        super().validate_project(args.project_id)

        if args.json is not None:
            dict_comments = annofabcli.common.cli.get_json_from_args(args.json)
            if not isinstance(dict_comments, dict):
                print(f"{self.COMMON_MESSAGE} argument --json: JSON形式が不正です。オブジェクトを指定してください。", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        elif args.csv is not None:
            try:
                dict_comments = read_comment_csv(args.csv, comment_type=CommentType.ONHOLD)
            except ValueError as e:
                print(f"{self.COMMON_MESSAGE} argument --csv: CSVの読み込みに失敗しました。 :: {e}", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        else:
            print(f"{self.COMMON_MESSAGE} --json または --csv のいずれかを指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        comments_for_task_list = convert_cli_comments(
            dict_comments,
            comment_type=CommentType.ONHOLD,
        )
        main_obj = PutCommentMain(self.service, project_id=args.project_id, comment_type=CommentType.ONHOLD, all_yes=self.all_yes)
        main_obj.add_comments_for_task_list(
            comments_for_task_list=comments_for_task_list,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    PutInspectionComment(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    # --jsonと--csvは相互排他的
    input_group = parser.add_mutually_exclusive_group(required=True)

    SAMPLE_JSON = {"task1": {"input_data1": [{"comment": "type属性が間違っています。"}]}}  # noqa: N806
    input_group.add_argument(
        "--json",
        type=str,
        help=(
            f"付与する保留コメントの情報をJSON形式で指定してください。``file://`` を先頭に付けると、JSON形式のファイルを指定できます。\n\n"
            f"各コメントには ``comment_id`` を指定することができます。省略した場合は自動的にUUIDv4が生成されます。\n\n"
            f"(ex)  ``{json.dumps(SAMPLE_JSON, ensure_ascii=False)}``"
        ),
    )

    input_group.add_argument(
        "--csv",
        type=Path,
        help=(
            "付与する保留コメントの内容をCSV形式で指定してください。\n"
            "CSVには以下の列が必要です：\n\n"
            " * ``task_id`` （必須）: タスクID\n"
            " * ``input_data_id`` （必須）: 入力データID\n"
            " * ``comment`` （必須）: コメント本文\n"
            " * ``annotation_id`` （任意）: 紐付けるアノテーションID\n"
            " * ``comment_id`` （任意）: コメントID（省略時はUUIDv4自動生成）\n"
        ),
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "put_onhold"
    subcommand_help = "保留コメントを付与します"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help)
    parse_args(parser)
    return parser
