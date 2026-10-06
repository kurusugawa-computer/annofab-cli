from __future__ import annotations

import argparse
import copy
import json
import logging
from typing import Any

import annofabapi
from annofabapi.models import InputDataType

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine, CommandLineWithConfirm, build_annofabapi_resource_and_login, get_json_from_args
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def read_option_json(option_json: str) -> dict[str, bool]:
    """更新するoptionのJSONを読み込み、キーと値を検証する。

    Args:
        option_json: JSON文字列、またはfile://付きのJSONファイルパス

    Returns:
        検証済みの更新項目

    Raises:
        TypeError: JSONオブジェクトでない場合、または値の型が不正な場合
        ValueError: 空のオブジェクト、または未知のキーが指定された場合
    """
    option = get_json_from_args(option_json)
    if not isinstance(option, dict):
        raise TypeError("`--option_json` にはJSONオブジェクトを指定してください。")
    if not option:
        raise ValueError("`--option_json` には更新する項目を1つ以上指定してください。")
    unexpected_keys = set(option) - {"can_overwrap"}
    if unexpected_keys:
        raise ValueError(f"`--option_json` に未知のキーが指定されています。 :: {sorted(unexpected_keys)}")
    if not isinstance(option["can_overwrap"], bool):
        raise TypeError("`can_overwrap` にはbooleanを指定してください。")
    return {"can_overwrap": option["can_overwrap"]}


def build_request_body_for_update_option(annotation_specs: dict[str, Any], *, option: dict[str, bool], comment: str | None) -> dict[str, Any]:
    """指定したoptionのキーだけ更新したリクエストボディを生成する。

    Args:
        annotation_specs: 既存のアノテーション仕様
        option: 更新する項目
        comment: 変更コメント。Noneの場合は自動生成する

    Returns:
        Annofab APIに渡すリクエストボディ
    """
    request_body = copy.deepcopy(annotation_specs)
    request_body.setdefault("option", {}).update(option)
    request_body["comment"] = comment if comment is not None else f"アノテーション仕様のoptionを更新しました。\n{json.dumps(option, ensure_ascii=False)}"
    request_body["last_updated_datetime"] = annotation_specs["updated_datetime"]
    return request_body


class UpdateOptionMain(CommandLineWithConfirm):
    """アノテーション仕様のoptionを更新する本体処理。"""

    def __init__(self, service: annofabapi.Resource, *, project_id: str, all_yes: bool) -> None:
        """更新対象と確認方法を設定する。

        Args:
            service: Annofab APIのリソース
            project_id: 更新対象プロジェクトID
            all_yes: 確認を省略するかどうか

        Returns:
            None
        """
        self.service = service
        """Annofab APIのリソース。"""
        self.project_id = project_id
        """更新対象プロジェクトID。"""
        super().__init__(all_yes)

    def update_option(self, *, option: dict[str, bool], comment: str | None = None) -> bool:
        """動画プロジェクトのoptionを確認後に更新する。

        Args:
            option: 検証済みの更新項目
            comment: 変更コメント

        Returns:
            更新した場合はTrue、変更がない場合や確認で中断した場合はFalse

        Raises:
            ValueError: 動画プロジェクトでない場合
        """
        project, _ = self.service.api.get_project(self.project_id)
        if project["input_data_type"] != InputDataType.MOVIE.value:
            raise ValueError("動画プロジェクトを指定してください。")
        annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        old_option = annotation_specs.get("option", {})
        changes = {key: value for key, value in option.items() if key not in old_option or old_option[key] != value}
        if not changes:
            logger.info("指定したoptionは現在値と同じため、更新をスキップします。")
            return False

        changes_text = "\n".join(f"{key}: {json.dumps(old_option.get(key))} → {json.dumps(value)}" for key, value in changes.items())
        logger.info(f"project_id='{self.project_id}' のアノテーション仕様のoptionを更新します。\n{changes_text}")
        if not self.confirm_processing(f"以下のoptionを更新します。\n{changes_text}\nよろしいですか？"):
            return False
        request_body = build_request_body_for_update_option(annotation_specs, option=option, comment=comment)
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info("アノテーション仕様のoptionを更新しました。")
        return True


class UpdateOption(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs update_option: error:"
    """コマンドのエラーメッセージの接頭辞。"""

    def main(self) -> None:
        """コマンドライン引数からoptionを読み込み、更新する。

        Args:
            なし

        Returns:
            None
        """
        args = self.args
        option = read_option_json(args.option_json)
        obj = UpdateOptionMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.update_option(option=option, comment=args.comment)


def parse_args(parser: argparse.ArgumentParser) -> None:
    """update_optionの引数を定義する。

    Args:
        parser: 引数を追加するパーサー

    Returns:
        None
    """
    ArgumentParser(parser).add_project_id()
    parser.add_argument(
        "--option_json",
        type=str,
        required=True,
        help=(
            "更新するoptionのJSONオブジェクトを指定します。指定したキーだけ更新し、省略したキーは現在値を保持します。"
            " ``file://`` を先頭に付けるとJSONファイルを指定できます。"
            ' 現在は ``can_overwrap`` のみ指定できます。（例） ``{"can_overwrap": false}``'
            " ``can_overwrap`` は動画プロジェクトで区間の重なりを許容するかどうかを示すbooleanです。"
            " 空のオブジェクト、未知のキー、不正な型の値は指定できません。"
        ),
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")
    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """update_optionを実行する。

    Args:
        args: コマンドライン引数

    Returns:
        None
    """
    service = build_annofabapi_resource_and_login(args)
    UpdateOption(service, AnnofabApiFacade(service), args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """update_optionのパーサーを生成する。

    Args:
        subparsers: 親パーサーのサブコマンド

    Returns:
        生成したパーサー
    """
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        "update_option",
        "アノテーション仕様のoptionを更新します。",
        description="動画プロジェクトのアノテーション仕様のoptionを、指定されたキーだけ更新します。",
    )
    parse_args(parser)
    return parser
