"""組織の利用状況詳細CSVをダウンロードします。"""

import argparse
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import annofabcli.common.cli
from annofabcli.common.cli import CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.organization.usage_status import year_month

logger = logging.getLogger(__name__)


class DownloadUsageStatusDetail(CommandLine):
    """利用状況詳細CSVを保存するコマンド。"""

    def main(self) -> None:
        """CSVを一時ファイルに取得し、成功した場合に出力先へ保存します。

        Args:
            なし。

        Returns:
            None。
        """
        args = self.args
        logger.info(f"組織'{args.organization}'の{args.year_month}の利用状況詳細CSVをダウンロードします。")
        csv_file, _ = self.service.api.get_organization_usage_status_detail(args.organization, args.year_month)
        output: Path = args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=output.parent) as temporary_dir:
            temporary_file = Path(temporary_dir) / "usage_status.csv"
            self.service.wrapper.download(csv_file["url"], temporary_file)
            temporary_file.replace(output)
        logger.info(f"利用状況詳細CSVを保存しました。 :: output='{output}'")


def main(args: argparse.Namespace) -> None:
    """コマンドを実行します。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    service = build_annofabapi_resource_and_login(args)
    DownloadUsageStatusDetail(service, AnnofabApiFacade(service), args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    """コマンドライン引数を登録します。

    Args:
        parser: 引数を登録するパーサー。

    Returns:
        None。
    """
    parser.add_argument("-org", "--organization", required=True, help="対象の組織名。組織管理者として実行してください。")
    parser.add_argument("--year_month", type=year_month, required=True, help="取得する利用状況の対象月（YYYY-MM）。")
    parser.add_argument("-o", "--output", type=Path, required=True, help="CSVファイルの保存先。既存ファイルはダウンロード成功後に上書きします。")
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """利用状況詳細ダウンロードのパーサーを作成します。

    Args:
        subparsers: コマンドを登録する親パーサー。

    Returns:
        作成したパーサー。
    """
    description = "指定した月の組織の利用状況詳細CSVをダウンロードします。APIが提供するCSVをそのまま保存します。"
    parser = annofabcli.common.cli.add_parser(subparsers, "download_usage_status_detail", "組織の利用状況詳細CSVをダウンロードします。", description)
    parse_args(parser)
    return parser
