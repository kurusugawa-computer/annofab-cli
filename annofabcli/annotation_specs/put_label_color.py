from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from typing import Any, Optional

import annofabapi

import annofabcli
import annofabcli.common.cli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


Color = tuple[int, int, int]
LabelColorDict = dict[str, Color]


@dataclass(frozen=True)
class Label:
    label_name_en: str
    label_id: str


class PuttingLabelColorMain(CommandLineWithConfirm):
    def __init__(self, service: annofabapi.Resource, project_id: str, *, all_yes: bool) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id
        CommandLineWithConfirm.__init__(self, all_yes)

    def create_request_body(self, label_color_dict: LabelColorDict) -> tuple[dict[str, Any], list[Label]]:
        """
        アノテーション仕様のリクエストボディと、変更対象のラベルの一覧を取得します。
        """
        request_body, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": 3})

        request_body["last_updated_datetime"] = request_body["updated_datetime"]

        changed_labels: list[Label] = []
        labels = request_body["labels"]
        for label_name_en, color in label_color_dict.items():
            target_labels = [e for e in labels if AnnofabApiFacade.get_label_name_en(e) == label_name_en]
            if len(target_labels) == 0:
                logger.warning(f"label_name_en='{label_name_en}'であるラベルは存在しません。")
                continue
            if len(target_labels) == 2:
                logger.warning(f"label_name_en='{label_name_en}'であるラベルは複数存在します。")

            for target_label in target_labels:
                new_color = {"red": color[0], "green": color[1], "blue": color[2]}
                if target_label["color"] != new_color:
                    target_label["color"] = new_color
                    changed_labels.append(
                        Label(
                            label_id=target_label["label_id"],
                            label_name_en=AnnofabApiFacade.get_label_name_en(target_label),
                        )
                    )

        return request_body, changed_labels

    def confirm_to_change_label_color(self, changed_labels: list[Label]) -> bool:
        confirm_message = f"以下のラベル({len(changed_labels)})件を変更しますか？"

        str_changed_labels = "\n".join([f" * label_name_en='{e.label_name_en}', label_id='{e.label_id}'" for e in changed_labels])
        confirm_message = confirm_message + "\n" + str_changed_labels
        return self.confirm_processing(confirm_message)

    def main(self, label_color: LabelColorDict, comment: Optional[str]) -> None:
        request_body, changed_labels = self.create_request_body(label_color)

        if len(changed_labels) == 0:
            logger.info("変更対象のラベルがなかった（`--json`で指定されたラベルの色は、アノテーション仕様と同じだった）ので、終了します。")
            return

        if comment is None:
            tmp_str_labels = ", ".join([e.label_name_en for e in changed_labels])
            comment = f"以下のラベルの色を変更しました。\n{tmp_str_labels}"

        request_body["comment"] = comment
        if not self.confirm_to_change_label_color(changed_labels):
            return

        self.service.api.put_annotation_specs(self.project_id, query_params={"v": 3}, request_body=request_body)
        logger.info("アノテーション仕様のラベルの色を変更しました。")


class PutLabelColor(CommandLine):
    def main(self) -> None:
        args = self.args
        label_color = get_json_from_args(args.json)

        if not isinstance(label_color, dict):
            print("annofabcli annotation_specs put_label_color: error: JSON形式が不正です。オブジェクトを指定してください。", file=sys.stderr)  # noqa: T201
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        main_obj = PuttingLabelColorMain(service=self.service, project_id=args.project_id, all_yes=args.yes)
        main_obj.main(label_color, comment=args.comment)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    JSON_SAMPLE = '{"label1":[255,255,255]}'  # noqa: N806
    parser.add_argument(
        "--json",
        type=str,
        required=True,
        help=(f"変更したいラベルの色をJSON形式で指定してください。keyがラベル英語名, valueがRGB値の配列です。\n(ex) ``{JSON_SAMPLE}`` \n``file://`` を先頭に付けるとjsonファイルを指定できます。"),
    )

    parser.add_argument(
        "--comment",
        type=str,
        help=("変更内容のコメントを指定してください。未指定の場合、自動でコメントが生成されます。"),
    )

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)

    PutLabelColor(service, facade, args).main()


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "put_label_color"

    subcommand_help = "ラベルの色を変更します。"

    epilog = "チェッカーロール、オーナーロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
