from __future__ import annotations

import argparse
import json
import sys

from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    PARALLELISM_CHOICES,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.input_data.update_metadata_of_input_data import Metadata, UpdateMetadataMain, validate_metadata


class UpdateMetadataPerInputData(CommandLine):
    """入力データごとに指定したメタデータを更新する。"""

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                "annofabcli input_data update_metadata_per_input_data: error: argument --parallelism: '--parallelism' を指定するときは、 '--yes' が必須です。",
                file=sys.stderr,
            )
            return False
        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        metadata_by_input_data_id: dict[str, Metadata] = annofabcli.common.cli.get_json_from_args(args.json)
        input_data_ids_containing_invalid_metadata = [input_data_id for input_data_id, metadata in metadata_by_input_data_id.items() if not validate_metadata(metadata)]
        if input_data_ids_containing_invalid_metadata:
            print(  # noqa: T201
                "annofabcli input_data update_metadata_per_input_data: error: argument --json: "
                "以下の入力データIDに対応するメタデータは不正な形式です。"
                "メタデータの値は文字列である必要があります。 :: "
                f"{input_data_ids_containing_invalid_metadata}",
                file=sys.stderr,
            )
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        super().validate_project(args.project_id, [ProjectMemberRole.OWNER])
        main_obj = UpdateMetadataMain(self.service, all_yes=args.yes)
        main_obj.update_metadata_of_input_data(
            args.project_id,
            metadata_by_input_data_id=metadata_by_input_data_id,
            overwrite_metadata=args.overwrite,
            parallelism=args.parallelism,
        )


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateMetadataPerInputData(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    sample_json = {"input_data1": {"country": "japan"}}
    parser.add_argument(
        "--json",
        type=str,
        required=True,
        help=(
            "キーが入力データID、値が設定するメタデータであるオブジェクトをJSON形式で指定してください。"
            "メタデータの値は文字列です。\n"
            f"(ex) '{json.dumps(sample_json)}'\n"
            "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="指定した場合、メタデータを上書きして更新します（すでに設定されているメタデータは削除されます）。指定しない場合、JSONに指定されたキーのみ更新されます。",
    )
    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "update_metadata_per_input_data"
    subcommand_help = "入力データごとにメタデータを更新します。"
    description = "入力データごとに指定したメタデータを更新します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
