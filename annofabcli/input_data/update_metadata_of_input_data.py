import argparse
import logging
import multiprocessing
import sys
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    AbstractCommandLineInterface,
    AbstractCommandLineWithConfirmInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
)

logger = logging.getLogger(__name__)


class UpdateMetadataMain(AbstractCommandLineWithConfirmInterface):
    def __init__(self, service: annofabapi.Resource, all_yes: bool = False):
        self.service = service
        AbstractCommandLineWithConfirmInterface.__init__(self, all_yes)

    def set_metadata_to_input_data(
        self,
        project_id: str,
        input_data_id: str,
        metadata: Dict[str, Any],
        overwrite_metadata: bool = False,
        input_data_index: Optional[int] = None,
    ) -> bool:
        logging_prefix = f"{input_data_index+1} 件目" if input_data_index is not None else ""

        input_data = self.service.wrapper.get_input_data_or_none(project_id, input_data_id)
        if input_data is None:
            logger.warning(f"{logging_prefix} 入力データは存在しないのでスキップします。input_data_id={input_data_id}")
            return False

        logger.debug(
            f"{logging_prefix} input_data_id={input_data['input_data_id']}, "
            f"input_data_name={input_data['input_data_name']}"
        )
        if not self.confirm_processing(f"入力データのメタデータを更新しますか？ input_data_id={input_data['input_data_id']}"):
            return False

        input_data["last_updated_datetime"] = input_data["updated_datetime"]
        if overwrite_metadata:
            input_data["metadata"] = metadata
        else:
            input_data["metadata"].update(metadata)

        self.service.api.put_input_data(project_id, input_data_id, request_body=input_data)
        logger.debug(f"{logging_prefix} 入力データを更新しました。input_data_id={input_data['input_data_id']}")
        return True

    def set_metadata_to_input_data_wrapper(
        self, tpl: Tuple[int, str], project_id: str, metadata: Dict[str, Any], overwrite_metadata: bool = False
    ):
        input_data_index, input_data_id = tpl
        return self.set_metadata_to_input_data(
            project_id,
            input_data_id,
            metadata=metadata,
            overwrite_metadata=overwrite_metadata,
            input_data_index=input_data_index,
        )

    def update_metadata_of_input_data(
        self,
        project_id: str,
        input_data_id_list: List[str],
        metadata: Dict[str, Any],
        overwrite_metadata: bool = False,
        parallelism: Optional[int] = None,
    ):
        if overwrite_metadata:
            logger.info(f"{len(input_data_id_list)} 件の入力データのmetadataを、{metadata} に変更します（上書き）。")
        else:
            logger.info(f"{len(input_data_id_list)} 件の入力データのmetadataに、{metadata} を追加します。")

        success_count = 0

        if parallelism is not None:
            partial_func = partial(
                self.set_metadata_to_input_data_wrapper,
                project_id=project_id,
                metadata=metadata,
                overwrite_metadata=overwrite_metadata,
            )
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(partial_func, enumerate(input_data_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            # 逐次処理
            for input_data_index, input_data_id in enumerate(input_data_id_list):
                result = self.set_metadata_to_input_data(
                    project_id,
                    input_data_id,
                    metadata=metadata,
                    overwrite_metadata=overwrite_metadata,
                    input_data_index=input_data_index,
                )
                if result:
                    success_count += 1

        logger.info(f"{success_count} / {len(input_data_id_list)} 件の入力データのmetadataを変更しました。")


class UpdateMetadata(AbstractCommandLineInterface):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli input_data update_metadata: error:"

        if args.parallelism is not None and not args.yes:
            print(
                f"{COMMON_MESSAGE} argument --parallelism: '--parallelism'を指定するときは、必ず ``--yes`` を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def main(self):
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        input_data_id_list = annofabcli.common.cli.get_list_from_args(args.input_data_id)
        metadata = annofabcli.common.cli.get_json_from_args(args.metadata)
        super().validate_project(args.project_id, [ProjectMemberRole.OWNER])
        main_obj = UpdateMetadataMain(self.service, all_yes=args.yes)
        main_obj.update_metadata_of_input_data(
            args.project_id,
            input_data_id_list,
            metadata,
            overwrite_metadata=args.overwrite,
            parallelism=args.parallelism,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateMetadata(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_input_data_id(required=True)

    parser.add_argument(
        "--metadata",
        required=True,
        type=str,
        help="入力データに設定する ``metadata`` をJSON形式で指定してください。メタデータの値は文字列です。" " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="指定した場合、メタデータを上書きして更新します（すでに設定されているメタデータは削除されます）。指定しない場合、 ``--metadata`` に指定されたキーのみ更新されます。",
    )

    parser.add_argument(
        "--parallelism", type=int, help="使用するプロセス数（並列度）を指定してください。指定する場合は必ず ``--yes`` を指定してください。指定しない場合は、逐次的に処理します。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "update_metadata"
    subcommand_help = "入力データのメタデータを更新します。"
    description = "入力データのメタデータを更新します。"
    epilog = "オーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(
        subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog
    )
    parse_args(parser)
    return parser
