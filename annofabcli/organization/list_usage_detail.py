"""組織のエディタ利用状況の明細を出力します。"""

import argparse
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.organization.usage_status import validate_period, year_month

logger = logging.getLogger(__name__)

SOURCE_COLUMNS = {"date": "date", "editorName": "editor_name", "projectId": "project_id", "accountId": "account_id", "editorUsageTime": "editor_usage_hour"}
"""APIが提供するCSVの列名と、CLIの出力項目名の対応。"""

CSV_DTYPES = {"date": "string", "editorName": "string", "projectId": "string", "accountId": "string", "editorUsageTime": "Float64"}
"""IDを文字列、エディタ利用時間を時間単位の数値として読み込む型。"""

CSV_COLUMNS = ("organization_id", "organization_name", "date", "editor_name", "project_id", "project_title", "account_id", "user_id", "username", "editor_usage_hour")
"""CSV・JSON共通の出力項目。"""


def get_target_months(start_month: str | None, end_month: str | None) -> list[str]:
    """省略された期間を補完し、開始月から終了月までの対象月を返します。

    Args:
        start_month: 開始月。省略時は終了月と同じ月。
        end_month: 終了月。省略時は日本時間の現在の月。

    Returns:
        開始月・終了月を含む、昇順の対象月一覧。

    Raises:
        AnnofabCliException: 開始月が終了月より後の場合。
    """
    if end_month is None:
        end_month = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m")
    if start_month is None:
        start_month = end_month
    validate_period(start_month, end_month, None)
    start_year, start_month_number = (int(value) for value in start_month.split("-"))
    end_year, end_month_number = (int(value) for value in end_month.split("-"))
    months = []
    for month_index in range(start_year * 12 + start_month_number - 1, end_year * 12 + end_month_number):
        year, zero_based_month = divmod(month_index, 12)
        months.append(f"{year:04d}-{zero_based_month + 1:02d}")
    return months


def read_usage_detail_csv(path: Path) -> pandas.DataFrame:
    """明細CSVを読み込み、列名を標準化します。

    Args:
        path: APIから取得した明細CSVのパス。

    Returns:
        列名を標準化した明細。エディタ利用時間の単位は時間です。
    """
    try:
        df = pandas.read_csv(path, usecols=list(SOURCE_COLUMNS), dtype=CSV_DTYPES, encoding="utf-8-sig", keep_default_na=False, na_values=[""])
    except pandas.errors.EmptyDataError:
        df = pandas.DataFrame(columns=list(SOURCE_COLUMNS)).astype(CSV_DTYPES)
    return df.rename(columns=SOURCE_COLUMNS)


def enrich_usage_detail(
    df: pandas.DataFrame,
    *,
    organization_id: str,
    organization_name: str,
    members: Sequence[Mapping[str, str]],
    projects: Sequence[Mapping[str, str]],
) -> pandas.DataFrame:
    """利用状況明細に組織・ユーザー・プロジェクト情報を付与します。

    Args:
        df: 列名を標準化した明細。
        organization_id: 組織ID。
        organization_name: 組織名。
        members: 現在の組織メンバー一覧。
        projects: 現在の組織配下プロジェクト一覧。

    Returns:
        出力項目を揃えた明細。対応するメンバーやプロジェクトがなければ補完項目は欠損値になります。
    """
    result = df.copy()
    result["organization_id"] = organization_id
    result["organization_name"] = organization_name
    result["user_id"] = result["account_id"].map({member["account_id"]: member["user_id"] for member in members}).astype("string")
    result["username"] = result["account_id"].map({member["account_id"]: member["username"] for member in members}).astype("string")
    result["project_title"] = result["project_id"].map({project["project_id"]: project["title"] for project in projects}).astype("string")
    return result[list(CSV_COLUMNS)]


class ListUsageDetail(CommandLine):
    """エディタ利用状況の明細をCSV・JSONで出力するコマンド。"""

    def main(self) -> None:
        """明細を取得してユーザー情報などを付与し、指定形式で出力します。

        Args:
            なし。

        Returns:
            None。
        """
        args = self.args
        months = get_target_months(args.start_month, args.end_month)
        frames = []
        with TemporaryDirectory() as temporary_dir:
            temporary_file = Path(temporary_dir) / "usage_status.csv"
            for index, month in enumerate(months, start=1):
                logger.info(f"{index}/{len(months)}: 組織'{args.organization}'の{month}のエディタ利用状況明細を取得します。")
                csv_file, _ = self.service.api.get_organization_usage_status_detail(args.organization, month)
                self.service.wrapper.download(csv_file["url"], temporary_file)
                month_df = read_usage_detail_csv(temporary_file)
                if not month_df.empty:
                    frames.append(month_df)
            df = pandas.concat(frames, ignore_index=True) if frames else pandas.DataFrame()
        if df.empty:
            self.print_according_to_format([], csv_columns=CSV_COLUMNS)
            logger.info("エディタ利用状況明細の件数: 0")
            return
        organization, _ = self.service.api.get_organization(args.organization)
        members = self.service.wrapper.get_all_organization_members(args.organization)
        projects = self.service.wrapper.get_all_projects_of_organization(args.organization)
        df = enrich_usage_detail(df, organization_id=organization["organization_id"], organization_name=args.organization, members=members, projects=projects)
        missing_member_count = df.loc[df["account_id"].notna() & df["user_id"].isna(), "account_id"].nunique()
        if missing_member_count:
            logger.warning(f"組織メンバーに見つからないアカウントが{missing_member_count}件あります。user_id・usernameは空欄またはnullで出力します。")
        self.print_according_to_format(df.to_dict(orient="records"), csv_columns=CSV_COLUMNS)
        logger.info(f"エディタ利用状況明細の件数: {len(df)}")


def main(args: argparse.Namespace) -> None:
    """コマンドを実行します。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    service = build_annofabapi_resource_and_login(args)
    ListUsageDetail(service, AnnofabApiFacade(service), args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    """コマンドライン引数を登録します。

    Args:
        parser: 引数を登録するパーサー。

    Returns:
        None。
    """
    parser.add_argument("-org", "--organization", required=True, help="対象の組織名。組織管理者として実行してください。")
    parser.add_argument("--start_month", type=year_month, help="明細の開始月（YYYY-MM、指定月を含む）。省略時は終了月と同じ月です。")
    parser.add_argument("--end_month", type=year_month, help="明細の終了月（YYYY-MM、指定月を含む）。省略時は日本時間（JST）の現在の月です。")
    argument_parser = ArgumentParser(parser)
    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """利用状況明細のパーサーを作成します。

    Args:
        subparsers: コマンドを登録する親パーサー。

    Returns:
        作成したパーサー。
    """
    description = (
        "指定した期間の組織のエディタ利用状況明細をCSVまたはJSONで出力します。省略時は日本時間の現在の月のみ取得します。現在のユーザー情報・プロジェクト名を付与します。利用時間の単位は時間です。"
    )
    parser = annofabcli.common.cli.add_parser(subparsers, "list_usage_detail", "組織のエディタ利用状況明細を出力します。", description)
    parse_args(parser)
    return parser
