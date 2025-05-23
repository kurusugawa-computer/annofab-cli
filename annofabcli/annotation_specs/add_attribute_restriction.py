from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
from typing import Any, Optional

import annofabapi

import annofabcli
import annofabcli.common.cli
from annofabcli.annotation_specs.attribute_restriction import AttributeRestrictionMessage, OutputFormat
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def create_comment_from_restriction_text(restriction_text_list: list[str]) -> str:
    """
    属性制約のテキストから、アノテーション仕様変更時のコメントを生成する
    """
    return "以下の属性制約を追加しました。\n" + "\n".join(restriction_text_list)


class AddAttributeRestrictionMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        all_yes: bool,
    ) -> None:
        self.service = service
        CommandLineWithConfirm.__init__(self, all_yes)
        self.project_id = project_id

    def add_restrictions(self, restrictions: list[dict[str, Any]], comment: Optional[str] = None) -> bool:
        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        old_restrictions = old_annotation_specs["restrictions"]

        msg_obj = AttributeRestrictionMessage(
            labels=old_annotation_specs["labels"],
            additionals=old_annotation_specs["additionals"],
            output_format=OutputFormat.TEXT,
            raise_if_not_found=True,
        )

        new_restrictions = []
        new_restriction_text_list = []
        for index, restriction in enumerate(restrictions):
            try:
                restriction_text = msg_obj.get_restriction_text(restriction["additional_data_definition_id"], restriction["condition"])
            except ValueError as e:
                logger.warning(f"{index + 1}件目 :: 次の属性制約は存在しないIDが含まれていたため、アノテーション仕様に追加しません。 :: restriction=`{restriction}`, error_message=`{e!s}`")
                continue

            if restriction in old_restrictions:
                logger.warning(f"{index + 1}件目 :: 次の属性制約は既に存在するため、アノテーション仕様に追加しません。  :: `{restriction_text}`")
                continue

            if not self.confirm_processing(f"次の属性制約を追加しますか？ :: `{restriction_text}`"):
                continue

            logger.debug(f"{index + 1}件目 :: 次の属性制約を追加します。 :: `{restriction_text}`")
            new_restrictions.append(restriction)
            new_restriction_text_list.append(restriction_text)

        if len(new_restrictions) == 0:
            logger.info("追加する属性制約はないため、アノテーション仕様を変更しません。")
            return False

        if not self.confirm_processing(f"{len(new_restrictions)} 件の属性制約を追加して、アノテーション仕様を変更します。よろしいですか？ "):
            return False

        request_body = copy.deepcopy(old_annotation_specs)
        request_body["restrictions"].extend(restrictions)
        if comment is None:
            comment = create_comment_from_restriction_text(new_restriction_text_list)
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(new_restrictions)} 件の属性制約をアノテーション仕様に追加しました。")
        return True


class AddAttributeRestriction(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs add_restriction: error:"

    def get_history_id_from_before_index(self, project_id: str, before: int) -> Optional[str]:
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        if before + 1 > len(histories):
            logger.warning(f"アノテーション仕様の履歴は{len(histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None
        history = histories[-(before + 1)]
        return history["history_id"]

    def main(self) -> None:
        args = self.args

        restrictions = get_json_from_args(args.json)
        if not isinstance(restrictions, list):
            print(f"{self.COMMON_MESSAGE}: error: JSON形式が不正です。オブジェクトの配列を指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        obj = AddAttributeRestrictionMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.add_restrictions(restrictions, comment=args.comment)


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-p", "--project_id", help="対象のプロジェクトのproject_idを指定します。", required=True)

    sample_json = [
        {
            "additional_data_definition_id": "a1",
            "condition": {"value": "true", "_type": "Equals"},
        }
    ]
    parser.add_argument(
        "--json",
        type=str,
        required=True,
        help=f"追加する属性の制約情報のJSONを指定します。JSON形式は ... を参照してください。\n(例) ``{json.dumps(sample_json)}``\n``file://`` を先頭に付けるとjsonファイルを指定できます。",
    )

    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更時に指定できるコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AddAttributeRestriction(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "add_attribute_restriction"

    subcommand_help = "アノテーション仕様に属性の制約を追加します。"
    description = subcommand_help + "アノテーション仕様画面では設定できない「属性間の制約」を追加するときに有用です。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
