import argparse
from collections.abc import Collection

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadFileTarget, DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade

MAX_PROJECT_COUNT = 4
"""一度に更新できるプロジェクト数の上限。"""


def validate_project_ids(project_ids: Collection[str]) -> None:
    """更新対象のプロジェクト数を検証する。

    Args:
        project_ids: 更新対象のプロジェクトID。

    Returns:
        None

    Raises:
        ValueError: プロジェクト数が1〜4個の範囲外の場合。
    """
    if not 1 <= len(project_ids) <= MAX_PROJECT_COUNT:
        raise ValueError(f"--project_id は1個以上{MAX_PROJECT_COUNT}個以下で指定してください。")


class UpdateDownloadFilesMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    def update_download_files(self, project_ids: Collection[str], targets: Collection[DownloadFileTarget]) -> None:
        """プロジェクト数を検証し、指定したファイルを並列に更新する。

        Args:
            project_ids: 対象のプロジェクトID。最大4個。
            targets: 更新対象。

        Returns:
            None
        """
        validate_project_ids(project_ids)
        DownloadingFile(self.service).update_download_files(project_ids, targets)


class UpdateDownloadFiles(CommandLine):
    def main(self) -> None:
        args = self.args
        for project_id in dict.fromkeys(args.project_id):
            self.require_project_access(project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        UpdateDownloadFilesMain(self.service).update_download_files(args.project_id, [DownloadFileTarget(target) for target in args.target])


def main(args: argparse.Namespace) -> None:
    try:
        validate_project_ids(args.project_id)
    except ValueError as e:
        args.root_parser.error(str(e))
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateDownloadFiles(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-p", "--project_id", nargs="+", required=True, help="対象のプロジェクトIDを最大4個指定します。")
    parser.add_argument(
        "--target",
        choices=[target.value for target in DownloadFileTarget],
        nargs="+",
        required=True,
        help="更新対象を1個以上指定します。task: タスク全件JSON、annotation: アノテーションZIP、input_data: 入力データ全件JSON。",
    )
    parser.set_defaults(subcommand_func=main)


def create_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "update_download_files"
    subcommand_help = "ダウンロード用ファイルを並列に更新し、すべての更新完了を待ちます。"
    description = (
        "指定したダウンロード用ファイルをAnnofab上で並列に更新します。ローカルへのダウンロードは行いません。"
        "60秒間隔で完了を確認し、各更新を最大6時間待ちます。"
        "一部の更新に失敗してもほかの更新の完了を待ち、いずれかが失敗またはタイムアウトした場合は非0の終了コードで終了します。"
    )
    parser = annofabcli.common.cli.create_parser(
        subparsers,
        subcommand_name,
        subcommand_help,
        description,
        epilog="オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。",
    )
    parse_args(parser)
    return parser
