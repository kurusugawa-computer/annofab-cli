"""組織の月別・日別利用状況を出力します。"""

import argparse
import logging
from collections.abc import Sequence

from annofabapi.pydantic_models.usage_status import UsageStatus
from annofabapi.pydantic_models.usage_status_by_day import UsageStatusByDay

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.organization.usage_status import validate_period, year_month

logger = logging.getLogger(__name__)

EDITOR_USAGE_COLUMNS = ("editor_usage.image_editor", "editor_usage.video_editor", "editor_usage.3d_editor")
"""エディタ利用時間（時間）のCSV列。"""

CSV_COLUMNS = ("organization_id", "year_month", "aggregation_period_from", "aggregation_period_to", "storage_usage", *EDITOR_USAGE_COLUMNS)
"""月別CSVの列。ストレージ利用量の単位はGB時。"""

DAILY_CSV_COLUMNS = ("organization_id", "date", "aggregation_period_from", "aggregation_period_to", "storage_usage", *EDITOR_USAGE_COLUMNS, "created_datetime")
"""日別CSVの列。"""


def create_csv_rows(usage_status_list: Sequence[UsageStatus | UsageStatusByDay]) -> list[dict[str, str | float | int | None]]:
    """エディタ別利用時間をCSVの列に展開します。

    Args:
        usage_status_list: 月別または日別の利用状況。

    Returns:
        CSV出力用のレコード一覧。未取得のエディタ利用時間は空欄になります。
    """
    rows: list[dict[str, str | float | int | None]] = []
    for usage in usage_status_list:
        row: dict[str, str | float | int | None] = {"organization_id": usage.organization_id}
        if isinstance(usage, UsageStatusByDay):
            row["date"] = usage.var_date
        else:
            row["year_month"] = usage.year_month
        row.update(aggregation_period_from=usage.aggregation_period_from, aggregation_period_to=usage.aggregation_period_to, storage_usage=usage.storage_usage)
        row.update(dict.fromkeys(EDITOR_USAGE_COLUMNS))
        row.update({f"editor_usage.{editor.editor_name}": editor.value for editor in usage.editor_usage})
        if isinstance(usage, UsageStatusByDay):
            row["created_datetime"] = usage.created_datetime
        rows.append(row)
    return rows


class ListUsageStatus(CommandLine):
    """組織の利用状況一覧を出力するコマンド。"""

    def main(self) -> None:
        """APIから利用状況を取得し、指定された形式で出力します。

        Args:
            なし。

        Returns:
            None。
        """
        args = self.args
        if args.year_month is not None:
            usage_status_list, _ = self.service.api.get_organization_usage_status(args.organization, args.year_month)
        else:
            query_params = {key: value for key, value in {"from": args.from_month, "to": args.to_month}.items() if value is not None}
            usage_status_list, _ = self.service.api.get_organization_usage_status_list(args.organization, query_params=query_params)
        logger.info(f"組織'{args.organization}'の利用状況一覧の件数: {len(usage_status_list)}")
        if args.format == OutputFormat.CSV.value:
            model = UsageStatusByDay if args.year_month is not None else UsageStatus
            rows = create_csv_rows([model.model_validate(usage) for usage in usage_status_list])
            columns = DAILY_CSV_COLUMNS if args.year_month is not None else CSV_COLUMNS
            self.print_according_to_format(rows, csv_columns=columns)
        else:
            self.print_according_to_format(usage_status_list)


def main(args: argparse.Namespace) -> None:
    """引数を検証してコマンドを実行します。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    validate_period(args.from_month, args.to_month, args.year_month)
    service = build_annofabapi_resource_and_login(args)
    ListUsageStatus(service, AnnofabApiFacade(service), args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    """コマンドライン引数を登録します。

    Args:
        parser: 引数を登録するパーサー。

    Returns:
        None。
    """
    parser.add_argument("-org", "--organization", required=True, help="対象の組織名。組織管理者として実行してください。")
    parser.add_argument("--from_month", type=year_month, help="月別一覧の開始月（YYYY-MM、当月を含む）。省略時はAPIの既定期間を使用します。")
    parser.add_argument("--to_month", type=year_month, help="月別一覧の終了月（YYYY-MM、当月を含む）。省略時はAPIの既定期間を使用します。")
    parser.add_argument("--year_month", type=year_month, help="日別一覧を取得する対象月（YYYY-MM）。--from_month、--to_monthとは同時に指定できません。")
    argument_parser = ArgumentParser(parser)
    argument_parser.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    argument_parser.add_output()
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """利用状況一覧のパーサーを作成します。

    Args:
        subparsers: コマンドを登録する親パーサー。

    Returns:
        作成したパーサー。
    """
    description = "組織の月別または日別の利用状況を出力します。エディタ利用時間の単位は時間、ストレージ利用量の単位はGB時です。"
    parser = annofabcli.common.cli.add_parser(subparsers, "list_usage_status", "組織の利用状況一覧を出力します。", description)
    parse_args(parser)
    return parser
