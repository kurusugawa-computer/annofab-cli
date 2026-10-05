"""プロジェクトのメンバ構成の差分を出力する。"""

import argparse
import logging

import pandas

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.project_member.compare_project_members import MEMBER_PROPERTIES, CompareProjectMembers, add_comparison_arguments

logger = logging.getLogger(__name__)

DIFF_COLUMNS = ["src_project_id", "dest_project_id", "user_id", "action", "skip_reason", *[f"{side}_{key}" for side in ("src", "dest") for key in MEMBER_PROPERTIES]]
"""差分の出力列。"""


class DiffProjectMembers(CompareProjectMembers):
    """同期によって揃えるメンバ構成の差分を表示する。"""

    def main(self) -> None:
        """差分をCSVまたはJSONに出力する。リソースは変更しない。

        Args:
            なし

        Returns:
            None
        """
        records: list[dict[str, object]] = []
        for project_id in dict.fromkeys(annofabcli.common.cli.get_list_from_args(self.args.dest_project_id)):
            records.extend(
                {
                    "src_project_id": self.args.src_project_id,
                    "dest_project_id": project_id,
                    "user_id": difference.user_id,
                    "action": difference.action,
                    "skip_reason": difference.skip_reason,
                    **{
                        f"{side}_{key}": member.get(key) if member is not None else None for side, member in (("src", difference.source), ("dest", difference.destination)) for key in MEMBER_PROPERTIES
                    },
                }
                for difference in self.get_differences(self.args.src_project_id, project_id)
            )
        logger.info(f"メンバ構成の差分: {len(records)} 件")
        if self.args.format == OutputFormat.CSV.value:
            self.print_csv(pandas.DataFrame(records, columns=DIFF_COLUMNS))
        else:
            self.print_according_to_format(records)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    DiffProjectMembers(service, AnnofabApiFacade(service), args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    parser = annofabcli.common.cli.add_parser(subparsers, "diff", "基準プロジェクトと複数プロジェクトのメンバ構成の差分を出力します。")
    add_comparison_arguments(parser)
    argument_parser = ArgumentParser(parser)
    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()
    parser.set_defaults(subcommand_func=main)
    return parser
