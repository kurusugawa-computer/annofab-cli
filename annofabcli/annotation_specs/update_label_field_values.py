from __future__ import annotations

import argparse
import copy
import logging
from collections.abc import Sequence
from typing import Any, cast

import annofabapi
from annofabapi.util.annotation_specs import AnnotationSpecsAccessor

import annofabcli.common.cli
from annofabcli.annotation_specs.utils import get_label_name_en, get_target_labels
from annofabcli.common.cli import (
    ArgumentParser,
    CommandLine,
    CommandLineWithConfirm,
    build_annofabapi_resource_and_login,
    get_json_from_args,
    get_list_from_args,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def create_comment_for_update_label_field_values(
    *,
    label_names: Sequence[str],
    field_values: dict[str, Any] | None,
    replace: bool,
    clear: bool,
) -> str:
    """
    ラベルのfield_values更新時のデフォルトコメントを生成する。

    Args:
        label_names: 更新対象ラベルの英語名一覧
        field_values: 更新するfield_values。 ``--clear`` 指定時はNone
        replace: 全置換かどうか
        clear: クリアかどうか

    Returns:
        アノテーション仕様変更コメント
    """
    labels_text = ", ".join(label_names)
    if clear:
        return f"以下のラベルの field_values をクリアしました。\n対象ラベル: {labels_text}"

    operation = "置換" if replace else "更新"
    assert field_values is not None
    field_value_keys = ", ".join(sorted(field_values.keys()))
    return f"以下のラベルの field_values を{operation}しました。\n対象ラベル: {labels_text}\nfield_value_keys: {field_value_keys}"


def validate_field_values_input(field_values: object) -> dict[str, Any]:
    """
    ``--field_values_json`` で指定された値を検証する。

    Args:
        field_values: JSONから読み込んだ値

    Returns:
        検証済みのfield_values

    Raises:
        TypeError: JSONオブジェクトでない場合
    """
    if not isinstance(field_values, dict):
        raise TypeError("`--field_values_json` にはJSONオブジェクトを指定してください。")
    return cast(dict[str, Any], field_values)


class UpdateLabelFieldValuesMain(CommandLineWithConfirm):
    """
    既存ラベルのfield_valuesを更新する本体処理。
    """

    def __init__(
        self,
        service: annofabapi.Resource,
        *,
        project_id: str,
        all_yes: bool,
    ) -> None:
        self.service = service
        self.project_id = project_id
        CommandLineWithConfirm.__init__(self, all_yes)

    def update_label_field_values(
        self,
        *,
        label_ids: Sequence[str] | None,
        label_name_ens: Sequence[str] | None,
        field_values: dict[str, Any] | None,
        replace: bool,
        clear: bool,
        comment: str | None = None,
    ) -> bool:
        """
        指定ラベルのfield_valuesを更新して、アノテーション仕様を更新する。

        Args:
            label_ids: 更新対象ラベルID一覧。未指定時はNone
            label_name_ens: 更新対象ラベル英語名一覧。未指定時はNone
            field_values: 更新するfield_values。 ``clear=True`` の場合はNone
            replace: field_values全体を置換するかどうか
            clear: field_valuesを空辞書にするかどうか
            comment: 変更コメント

        Returns:
            更新を実行した場合はTrue、確認で中断した場合はFalse

        Raises:
            ValueError: 入力値や既存アノテーション仕様との整合性が不正な場合
        """
        if clear and replace:
            raise ValueError("`--clear` と `--replace` は同時に指定できません。")
        if not clear and field_values is None:
            raise ValueError("`field_values` を指定してください。")

        old_annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "3"})
        annotation_specs_accessor = AnnotationSpecsAccessor(old_annotation_specs)
        target_labels = get_target_labels(annotation_specs_accessor, label_ids=label_ids, label_name_ens=label_name_ens)
        label_names = [get_label_name_en(label) for label in target_labels]

        operation = "クリア" if clear else "置換" if replace else "更新"
        confirm_message = f"{len(target_labels)} 件のラベルの field_values を{operation}します。対象ラベル={label_names}。よろしいですか？"
        if not self.confirm_processing(confirm_message):
            return False

        request_body = copy.deepcopy(old_annotation_specs)
        target_label_id_set = {label["label_id"] for label in target_labels}
        for label in request_body["labels"]:
            if label["label_id"] not in target_label_id_set:
                continue

            if clear:
                label["field_values"] = {}
            elif replace:
                label["field_values"] = copy.deepcopy(field_values)
            else:
                merged_field_values = copy.deepcopy(label.get("field_values", {}))
                assert field_values is not None
                merged_field_values.update(copy.deepcopy(field_values))
                label["field_values"] = merged_field_values

        if comment is None:
            comment = create_comment_for_update_label_field_values(
                label_names=label_names,
                field_values=field_values,
                replace=replace,
                clear=clear,
            )
        request_body["comment"] = comment
        request_body["last_updated_datetime"] = old_annotation_specs["updated_datetime"]
        self.service.api.put_annotation_specs(self.project_id, query_params={"v": "3"}, request_body=request_body)
        logger.info(f"{len(target_labels)} 件のラベルの field_values を{operation}しました。")
        return True


class UpdateLabelFieldValues(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_specs update_label_field_values: error:"

    def main(self) -> None:
        """
        コマンドライン引数を解釈し、ラベルのfield_values更新処理を実行する。
        """
        args = self.args

        if args.clear:
            field_values = None
        else:
            field_values = validate_field_values_input(get_json_from_args(args.field_values_json))

        label_ids = get_list_from_args(args.label_id)
        label_name_ens = get_list_from_args(args.label_name_en)

        obj = UpdateLabelFieldValuesMain(self.service, project_id=args.project_id, all_yes=args.yes)
        obj.update_label_field_values(
            label_ids=label_ids,
            label_name_ens=label_name_ens,
            field_values=field_values,
            replace=args.replace,
            clear=args.clear,
            comment=args.comment,
        )


def parse_args(parser: argparse.ArgumentParser) -> None:
    """
    ``update_label_field_values`` サブコマンドの引数を定義する。

    Args:
        parser: 引数を追加するArgumentParser
    """
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()

    label_group = parser.add_mutually_exclusive_group(required=True)
    label_group.add_argument(
        "--label_name_en",
        type=str,
        nargs="+",
        help="更新する対象ラベルの英語名。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )
    label_group.add_argument(
        "--label_id",
        type=str,
        nargs="+",
        help="更新する対象ラベルのlabel_id。複数指定できます。 ``file://`` を先頭に付けると一覧ファイルを指定できます。",
    )

    update_group = parser.add_mutually_exclusive_group(required=True)
    update_group.add_argument(
        "--field_values_json",
        type=str,
        help=(
            "更新するfield_valuesのJSONオブジェクト。 ``file://`` を先頭に付けるとJSONファイルを指定できます。field_valuesのフォーマットはWebAPIの ``AnnotationTypeFieldValue`` を参照してください。"
        ),
    )
    update_group.add_argument(
        "--clear",
        action="store_true",
        help="対象ラベルの field_values を空辞書に更新します。",
    )

    parser.add_argument(
        "--replace",
        action="store_true",
        help="既存の field_values にマージせず、指定したJSONオブジェクトで field_values 全体を置換します。",
    )
    parser.add_argument("--comment", type=str, help="アノテーション仕様の変更内容を説明するコメント。未指定の場合、自動でコメントが生成されます。")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    """
    ``update_label_field_values`` コマンドのエントリポイント。

    Args:
        args: コマンドライン引数
    """
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UpdateLabelFieldValues(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """
    ``annotation_specs update_label_field_values`` 用のparserを生成する。

    Args:
        subparsers: 親parserのsubparsers

    Returns:
        生成したArgumentParser
    """
    subcommand_name = "update_label_field_values"
    subcommand_help = "アノテーション仕様の既存ラベルの field_values を更新します。"
    description = "アノテーション仕様の既存ラベルに設定された field_values を、マージ・置換・クリアのいずれかで更新します。field_values にはサイズ制約や許容誤差範囲などの情報を設定できます。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
    return parser
