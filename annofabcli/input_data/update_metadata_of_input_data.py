from __future__ import annotations

import argparse
import copy
import json
import logging
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
from annofabcli.common.input_data_metadata import (
    UpdateMetadataMain,
    validate_metadata,
)

logger = logging.getLogger(__name__)

DEPRECATED_METADATA_BY_INPUT_DATA_ID_MESSAGE = (
    "[DEPRECATED] :: '--metadata_by_input_data_id' は非推奨です。代わりに `input_data update_metadata_per_input_data --json` を使用してください。"
    " '--metadata_by_input_data_id' オプションは2027/01/01以降に廃止予定です。"
)


class UpdateMetadata(CommandLine):
    COMMON_MESSAGE = "annofabcli input_data update_metadata: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.parallelism is not None and not args.yes:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        if args.metadata is not None and args.input_data_id is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --input_data_id: '--metadata' を指定するときは、 '--input_data_id' が必須です。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id) if args.input_data_id is not None else None

        if args.metadata is not None:
            metadata = annofabcli.common.cli.get_json_from_args(args.metadata)
            if not validate_metadata(metadata):
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --metadata: メタデータは不正な形式です。メタデータの値は文字列である必要があります。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            assert input_data_id_list is not None, "'--metadata'を指定したときは'--input_data_id'は必須です。"
            metadata_by_input_data_id = {input_data_id: copy.deepcopy(metadata) for input_data_id in input_data_id_list}

        elif args.metadata_by_input_data_id is not None:
            logger.warning(DEPRECATED_METADATA_BY_INPUT_DATA_ID_MESSAGE)
            metadata_by_input_data_id = annofabcli.common.cli.get_json_from_args(args.metadata_by_input_data_id)

            input_data_ids_containing_invalid_metadata = []
            for input_data_id, metadata in metadata_by_input_data_id.items():
                if not validate_metadata(metadata):
                    input_data_ids_containing_invalid_metadata.append(input_data_id)

            if len(input_data_ids_containing_invalid_metadata) > 0:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --metadata: 以下の入力データIDに対応するメタデータは不正な形式です。"
                    f"メタデータの値は文字列である必要があります。 :: {input_data_ids_containing_invalid_metadata}",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            if input_data_id_list is not None:
                metadata_by_input_data_id = {input_data_id: metadata for input_data_id, metadata in metadata_by_input_data_id.items() if input_data_id in input_data_id_list}
        else:
            raise RuntimeError("'--metadata'か'--metadata_by_input_data_id'のどちらかを指定する必要があります。")

        super().require_project_access(args.project_id, [ProjectMemberRole.OWNER])
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
    UpdateMetadata(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_input_data_id(required=False)

    metadata_group_parser = parser.add_mutually_exclusive_group(required=True)
    metadata_group_parser.add_argument(
        "--metadata",
        type=str,
        help="入力データに設定する ``metadata`` をJSON形式で指定してください。メタデータの値は文字列です。 ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    sample_metadata_by_input_data_id = {"input_data1": {"country": "japan"}}
    metadata_group_parser.add_argument(
        "--metadata_by_input_data_id",
        type=str,
        help=(
            "[DEPRECATED] キーが入力データID, 値がメタデータ( ``--metadata`` 参照)であるオブジェクトをJSON形式で指定してください。\n"
            "代わりに ``input_data update_metadata_per_input_data --json`` を使用してください。\n"
            "このオプションは2027/01/01以降に廃止予定です。\n"
            f"(ex) '{json.dumps(sample_metadata_by_input_data_id)}'\n"
            "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。"
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="指定した場合、メタデータを上書きして更新します（すでに設定されているメタデータは削除されます）。指定しない場合、 ``--metadata`` に指定されたキーのみ更新されます。",
    )

    parser.add_argument(
        "--parallelism",
        type=int,
        choices=PARALLELISM_CHOICES,
        help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "update_metadata"
    subcommand_help = "入力データのメタデータを更新します。"
    description = "入力データのメタデータを更新します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
