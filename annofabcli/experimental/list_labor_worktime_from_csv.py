import argparse
import logging
from pathlib import Path
from typing import List, Optional

import pandas

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import (
    AbstractCommandLineWithoutWebapiInterface,
    ArgumentParser,
    build_annofabapi_resource_and_login,
    get_list_from_args,
)
from annofabcli.common.utils import print_csv
from annofabcli.experimental.list_labor_worktime import (
    FormatTarget,
    create_df_from_intermediate,
    filter_df_intermediate,
)

logger = logging.getLogger(__name__)


def list_labor_worktime_from_csv(
    csv: Path,
    format_target: FormatTarget,
    *,
    project_id_list: Optional[List[str]] = None,
    user_id_list: Optional[List[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    output: Optional[Path] = None,
):
    df_intermediate = pandas.read_csv(csv)
    df_intermediate = filter_df_intermediate(
        df_intermediate,
        project_id_list=project_id_list,
        user_id_list=user_id_list,
        start_date=start_date,
        end_date=end_date,
    )

    df_output = create_df_from_intermediate(df_intermediate, format_target=format_target)
    print_csv(df_output, str(output) if output is not None else None)


class ListLaborWorktimeFormCsv(AbstractCommandLineWithoutWebapiInterface):
    def main(self):
        args = self.args

        project_id_list = get_list_from_args(args.project_id) if args.project_id is not None else None
        user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None

        list_labor_worktime_from_csv(
            csv=args,
            format_target=FormatTarget(args.format),
            project_id_list=project_id_list,
            user_id_list=user_id_list,
            start_date=args.start_date,
            end_date=args.end_date,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListLaborWorktimeFormCsv(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    parser.add_argument(
        "--csv", type=Path, help="'annofabcli experimental list_labor_worktime --format intermediate'の出力結果であるCSV"
    )

    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        help="集計対象のプロジェクトのproject_idを指定します。\n" "`file://`を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )
    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        help="集計対象のユーザのuser_idを指定します。\n" "`file://`を先頭に付けると、user_idの一覧が記載されたファイルを指定できます。",
    )
    parser.add_argument("--start_date", type=str, help="集計開始日(YYYY-mm-dd)")
    parser.add_argument("--end_date", type=str, help="集計終了日(YYYY-mm-dd)")

    format_choices = [e.value for e in FormatTarget]
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=format_choices,
        default="intermediate",
        help="出力する際のフォーマットを指定してください。\n"
        "・details: 日毎/人毎の詳細な値を出力します。\n"
        "・total: 期間中の合計値だけを出力します。\n"
        "・by_user:人毎の集計の合計値を出力します。\n"
        "・column_list:列固定で詳細な値を出力します。\n"
        "・column_list_per_project: 列固定で、日、メンバ、AnnoFabプロジェクトごとの作業時間を出力します。\n"
        "・intermediate: `annofabcli experimental list_labor_worktime_from_csv`コマンドに渡せる中間ファイルを出力します。\n",
    )

    argument_parser.add_output(required=False)

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_labor_worktime_from_csv"
    subcommand_help = "'annofabcli experimental list_labor_worktime --format intermediate'で出力したCSVを整形します。"
    description = "'annofabcli experimental list_labor_worktime --format intermediate'で出力したCSVを整形します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
