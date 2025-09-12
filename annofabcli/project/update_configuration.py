import argparse
import copy
import logging
from typing import Any, Optional

import annofabapi
import requests

import annofabcli
from annofabcli.common.cli import CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_json_from_args, get_list_from_args
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class UpdateProjectConfigurationMain(CommandLineWithConfirm):
    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        all_yes: bool = False,
    ) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)
        super().__init__(all_yes)

    def update_configuration_for_project(self, project_id: str, configuration: dict[str, Any]) -> bool:
        """
        指定されたプロジェクトの設定を更新する。

        Args:
            project_id: プロジェクトID
            configuration: 更新する設定（既存設定に対する部分的な更新）

        Returns:
            更新に成功した場合はTrue、失敗またはスキップした場合はFalse
        """
        project = self.service.wrapper.get_project_or_none(project_id)
        if project is None:
            logger.warning(f"project_id='{project_id}'のプロジェクトは存在しないので、スキップします。")
            return False

        project_name = project["title"]

        # 既存の設定を取得し、新しい設定をマージする
        current_configuration = project.get("configuration", {})
        updated_configuration = copy.deepcopy(current_configuration)
        updated_configuration.update(configuration)

        # 設定に変更がない場合はスキップ
        if current_configuration == updated_configuration:
            logger.info(f"project_id='{project_id}'のプロジェクト設定に変更がないため、スキップします。 :: project_name='{project_name}'")
            return False

        if not self.confirm_processing(f"project_id='{project_id}'のプロジェクト設定を更新しますか？ :: project_name='{project_name}'"):
            return False

        request_body = copy.deepcopy(project)
        request_body["configuration"] = updated_configuration
        request_body["last_updated_datetime"] = project["updated_datetime"]

        try:
            _, _ = self.service.api.put_project(project_id, request_body=request_body, query_params={"v": "2"})
            logger.info(f"project_id='{project_id}'のプロジェクト設定を更新しました。 :: project_name='{project_name}'")
        except requests.HTTPError:
            logger.warning(f"project_id='{project_id}'のプロジェクト設定の更新でHTTPエラーが発生しました。 :: project_name='{project_name}'", exc_info=True)
            return False
        else:
            return True

    def update_configuration_for_project_list(self, project_id_list: list[str], configuration: dict[str, Any]) -> tuple[int, int, int]:
        """
        複数のプロジェクトの設定を更新する。

        Args:
            project_id_list: プロジェクトIDのリスト
            configuration: 更新する設定

        Returns:
            (成功件数, スキップ件数, 失敗件数)のタプル
        """
        logger.info(f"{len(project_id_list)} 件のプロジェクトの設定を更新します。")

        success_count = 0
        skip_count = 0
        failure_count = 0

        for index, project_id in enumerate(project_id_list, start=1):
            try:
                logger.debug(f"{index}/{len(project_id_list)} 件目: project_id='{project_id}' の設定を更新します。")
                result = self.update_configuration_for_project(project_id, configuration)
                if result:
                    success_count += 1
                else:
                    skip_count += 1

                # 進捗をログ出力
                if index % 10 == 0 or index == len(project_id_list):
                    logger.info(f"{index}/{len(project_id_list)} 件のプロジェクトの処理が完了しました。")

            except Exception:
                failure_count += 1
                logger.warning(f"project_id='{project_id}'の設定更新で予期しないエラーが発生しました。", exc_info=True)

        logger.info(f"プロジェクト設定の更新が完了しました。成功: {success_count}件, スキップ: {skip_count}件, 失敗: {failure_count}件")
        return success_count, skip_count, failure_count


class UpdateProjectConfiguration(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id_list = get_list_from_args(args.project_id)
        configuration = get_json_from_args(args.configuration)

        if configuration:
            logger.error("--configuration パラメータで有効な設定を指定してください。")
            return

        main_obj = UpdateProjectConfigurationMain(self.service, all_yes=args.yes)
        success_count, _skip_count, _failure_count = main_obj.update_configuration_for_project_list(project_id_list=project_id_list, configuration=configuration)

        if success_count == 0:
            logger.info("プロジェクト設定は更新されませんでした。")


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateProjectConfiguration(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=True,
        nargs="+",
        help="変更対象プロジェクトのproject_idを指定します。 ``file://`` を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--configuration",
        type=str,
        required=True,
        help="更新するプロジェクト設定をJSON形式で指定します。既存の設定に対して部分的な更新を行います。"
        "JSONの構造については https://annofab.com/docs/api/#operation/putProject のリクエストボディ'configuration'を参照してください。\n"
        "``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "update_configuration"
    subcommand_help = "複数のプロジェクトの設定を一括で更新します。"
    epilog = "プロジェクトのオーナロールを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
