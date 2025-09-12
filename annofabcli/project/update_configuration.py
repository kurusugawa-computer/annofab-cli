import argparse
import copy
import logging
from typing import Any, Optional

import annofabapi

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

    def update_configuration_for_project(self, project_id: str, configuration: dict[str, Any], *, project_index: Optional[int] = None) -> bool:
        """
        指定されたプロジェクトの設定を更新する。

        Args:
            project_id: プロジェクトID
            configuration: 更新する設定（既存設定に対する部分的な更新）
            project_index: プロジェクトのインデックス（ログメッセージ用）

        Returns:
            True: プロジェクトの設定を更新した。
            False: 何らかの理由でプロジェクトの設定を更新していない
        """
        # ログメッセージの先頭の変数
        log_prefix = f"project_id='{project_id}' :: "
        if project_index is not None:
            log_prefix = f"{project_index + 1}件目 :: {log_prefix}"

        project = self.service.wrapper.get_project_or_none(project_id)
        if project is None:
            logger.warning(f"{log_prefix}プロジェクトは存在しないので、スキップします。")
            return False

        project_name = project["title"]

        # 既存の設定を取得し、新しい設定をマージする
        current_configuration = project["configuration"]
        updated_configuration = copy.deepcopy(current_configuration)
        updated_configuration.update(configuration)

        # 設定に変更がない場合はスキップ
        if current_configuration == updated_configuration:
            logger.debug(f"{log_prefix}プロジェクト設定に変更がないため、スキップします。 :: project_name='{project_name}'")
            return False

        if not self.confirm_processing(f"{log_prefix}プロジェクト設定を更新しますか？ :: project_name='{project_name}'"):
            return False

        request_body = copy.deepcopy(project)
        request_body["configuration"] = updated_configuration
        request_body["last_updated_datetime"] = project["updated_datetime"]
        request_body["status"] = project["project_status"]

        _, _ = self.service.api.put_project(project_id, request_body=request_body, query_params={"v": "2"})
        logger.debug(f"{log_prefix}プロジェクト設定を更新しました。 :: project_name='{project_name}'")
        return True

    def update_configuration_for_project_list(self, project_id_list: list[str], configuration: dict[str, Any]) -> None:
        """
        複数のプロジェクトの設定を更新する。

        Args:
            project_id_list: プロジェクトIDのリスト
            configuration: 更新する設定

        """
        logger.info(f"{len(project_id_list)} 件のプロジェクトの設定を更新します。")

        success_count = 0
        skip_count = 0
        failure_count = 0

        for index, project_id in enumerate(project_id_list):
            try:
                if (index + 1) % 1000 == 0:
                    logger.info(f"{index + 1} / {len(project_id_list)} 件目のプロジェクトの設定を更新中...")

                result = self.update_configuration_for_project(project_id, configuration, project_index=index - 1)
                if result:
                    success_count += 1
                else:
                    skip_count += 1

            except Exception:
                failure_count += 1
                logger.warning(f"{index + 1}件目 :: project_id='{project_id}'の設定更新で予期しないエラーが発生しました。", exc_info=True)

        logger.info(f"{success_count}/{len(project_id_list)}件のプロジェクトの設定の更新が完了しました。 :: スキップ: {skip_count}件, 失敗: {failure_count}件")


class UpdateProjectConfiguration(CommandLine):
    def main(self) -> None:
        args = self.args
        project_id_list = get_list_from_args(args.project_id)
        configuration = get_json_from_args(args.configuration)

        main_obj = UpdateProjectConfigurationMain(self.service, all_yes=args.yes)
        main_obj.update_configuration_for_project_list(project_id_list=project_id_list, configuration=configuration)


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
