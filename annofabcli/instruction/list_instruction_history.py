import argparse
import logging
from typing import Any

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.visualize import AddProps

logger = logging.getLogger(__name__)


class ListInstructionHistories(CommandLine):
    @staticmethod
    def _add_properties_to_instruction(visualize: AddProps, instruction_history: dict[str, Any]) -> dict[str, Any]:
        """
        作業ガイド履歴に、一覧表示用のキーを追加する。

        以下のキーを追加する。
        * user_id
        * username

        Args:
            visualize: プロジェクトメンバ情報を解決するオブジェクト
            instruction_history: 作業ガイド履歴

        Returns:
            情報が追加された作業ガイド履歴
        """
        account_id = instruction_history["account_id"]
        member = visualize.get_project_member_from_account_id(account_id) if account_id is not None else None
        instruction_history["user_id"] = member["user_id"] if member is not None else None
        instruction_history["username"] = member["username"] if member is not None else None
        return instruction_history

    def get_instruction_histories(self, project_id: str) -> list[dict[str, Any]]:
        # limitを指定する理由：上限がわからないので大きい値を指定する
        histories, _ = self.service.api.get_instruction_history(project_id, query_params={"limit": 200})
        visualize = AddProps(self.service, project_id)
        return [self._add_properties_to_instruction(visualize, e) for e in histories]

    def main(self) -> None:
        args = self.args
        project_id = args.project_id
        super().validate_project(project_id)

        histories = self.get_instruction_histories(project_id)
        self.print_according_to_format(histories)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListInstructionHistories(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    argument_parser.add_output()

    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_history"
    subcommand_help = "作業ガイドの変更履歴を出力します。"
    description = "作業ガイドの変更履歴を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
