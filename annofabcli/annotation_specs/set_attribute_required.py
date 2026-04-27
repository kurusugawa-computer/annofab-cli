from __future__ import annotations

import argparse

import annofabcli.common.cli
from annofabcli.annotation_specs.attribute_required import AttributeRequiredMain
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade


class SetAttributeRequired(CommandLine):
    """
    属性を必須にするコマンド。
    """

    def main(self) -> None:
        args = self.args
        attribute_ids = get_list_from_args(args.attribute_id) if args.attribute_id is not None else None
        attribute_name_ens = get_list_from_args(args.attribute_name_en) if args.attribute_name_en is not None else None

        obj = AttributeRequiredMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.set_attribute_required(
            attribute_ids=attribute_ids,
            attribute_name_ens=attribute_name_ens,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    attribute_group = parser.add_mutually_exclusive_group(required=True)
    attribute_group.add_argument(
        "--attribute_id",
        type=str,
        nargs="+",
        help="必須にする対象属性の属性ID。1個だけ指定して ``file://`` を先頭に付けると、属性IDを1行ずつ記載したファイルを指定できます。",
    )
    attribute_group.add_argument(
        "--attribute_name_en",
        type=str,
        nargs="+",
        help="必須にする対象属性の英語名。1個だけ指定して ``file://`` を先頭に付けると、属性名(英語)を1行ずつ記載したファイルを指定できます。",
    )

    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    SetAttributeRequired(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "set_attribute_required"

    subcommand_help = "属性の必須制約を設定します。"
    description = subcommand_help
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
