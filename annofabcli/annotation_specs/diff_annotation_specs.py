from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import annofabcli.common.cli
from annofabcli.annotation_specs.diff import (
    AnnotationSpecsDiffOutputFormat,
    create_annotation_specs_diff,
    format_annotation_specs_diff_as_text,
)
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import output_string, print_json

logger = logging.getLogger(__name__)


def _add_annotation_specs_source_arguments(parser: argparse.ArgumentParser, *, prefix: str) -> None:
    source_group = parser.add_argument_group(f"{prefix} side")
    required_group = source_group.add_mutually_exclusive_group(required=True)
    required_group.add_argument(
        f"--{prefix}_project_id",
        help="比較対象のプロジェクトのproject_idを指定します。APIで取得したアノテーション仕様情報を元に比較します。",
    )
    required_group.add_argument(
        f"--{prefix}_annotation_specs_json",
        type=Path,
        help="比較対象のアノテーション仕様JSONを指定します。JSONファイルに記載された情報を元に比較します。",
    )

    history_group = source_group.add_mutually_exclusive_group()
    history_group.add_argument(
        f"--{prefix}_history_id",
        type=str,
        help="比較対象のアノテーション仕様のhistory_idを指定してください。指定しない場合は、最新のアノテーション仕様を参照します。",
    )
    history_group.add_argument(
        f"--{prefix}_before",
        type=int,
        help="比較対象のアノテーション仕様が、最新よりいくつ前かを指定してください。たとえば ``1`` を指定した場合、最新より1個前のアノテーション仕様を参照します。",
    )


class AnnotationSpecsDiffCommand(CommandLine):
    """アノテーション仕様の差分を出力する。"""

    COMMON_MESSAGE = "annofabcli annotation_specs diff: error:"

    def get_history_id_from_before_index(self, project_id: str, before: int) -> str | None:
        histories, _ = self.service.api.get_annotation_specs_histories(project_id)
        sorted_histories = sorted(histories, key=lambda x: x["updated_datetime"], reverse=True)
        if before + 1 > len(sorted_histories):
            logger.warning(f"アノテーション仕様の履歴は{len(sorted_histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
            return None
        return sorted_histories[before]["history_id"]

    def get_annotation_specs_from_source(self, *, prefix: str) -> dict[str, Any]:
        project_id = getattr(self.args, f"{prefix}_project_id")
        annotation_specs_json = getattr(self.args, f"{prefix}_annotation_specs_json")
        history_id = getattr(self.args, f"{prefix}_history_id")
        before = getattr(self.args, f"{prefix}_before")

        if annotation_specs_json is not None:
            if history_id is not None or before is not None:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --{prefix}_history_id/--{prefix}_before: '--{prefix}_annotation_specs_json' を指定したときは指定できません。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            with annotation_specs_json.open(encoding="utf-8") as f:
                return json.load(f)

        assert project_id is not None
        resolved_history_id = history_id
        if before is not None:
            resolved_history_id = self.get_history_id_from_before_index(project_id, before)
            if resolved_history_id is None:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --{prefix}_before: 最新より{before}個前のアノテーション仕様は見つかりませんでした。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        query_params = {"v": "3"}
        if resolved_history_id is not None:
            query_params["history_id"] = resolved_history_id
        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params=query_params)
        return annotation_specs

    def main(self) -> None:
        left_specs = self.get_annotation_specs_from_source(prefix="left")
        right_specs = self.get_annotation_specs_from_source(prefix="right")
        targets = set(self.args.target) if self.args.target is not None else {"labels", "attributes", "attribute_restrictions"}
        diff = create_annotation_specs_diff(left_specs, right_specs, targets=targets)
        output_format = AnnotationSpecsDiffOutputFormat(self.args.format)

        if output_format == AnnotationSpecsDiffOutputFormat.TEXT:
            output_string(format_annotation_specs_diff_as_text(diff, left_specs=left_specs, right_specs=right_specs, detail=False), self.args.output)
            return

        if output_format == AnnotationSpecsDiffOutputFormat.DETAIL_TEXT:
            output_string(format_annotation_specs_diff_as_text(diff, left_specs=left_specs, right_specs=right_specs, detail=True), self.args.output)
            return

        if output_format == AnnotationSpecsDiffOutputFormat.JSON:
            print_json(diff.model_dump(exclude_none=True), is_pretty=False, output=self.args.output)
            return

        if output_format == AnnotationSpecsDiffOutputFormat.PRETTY_JSON:
            print_json(diff.model_dump(exclude_none=True), is_pretty=True, output=self.args.output)
            return

        raise RuntimeError(f"未対応の出力フォーマットです。 :: format='{self.args.format}'")


def parse_args(parser: argparse.ArgumentParser) -> None:
    _add_annotation_specs_source_arguments(parser, prefix="left")
    _add_annotation_specs_source_arguments(parser, prefix="right")

    parser.add_argument(
        "--target",
        nargs="+",
        choices=["labels", "attributes", "attribute_restrictions"],
        help="出力対象の差分を指定します。指定しない場合はすべて出力します。",
    )
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=[e.value for e in AnnotationSpecsDiffOutputFormat],
        default=AnnotationSpecsDiffOutputFormat.TEXT.value,
        help=("出力フォーマット\n\n* text: 差分項目のみを表示する\n* detail_text: 差分項目と変更前後の値を表示する\n* json: 差分情報をJSONで出力する\n* pretty_json: 差分情報を整形JSONで出力する\n"),
    )
    parser.add_argument("--output", type=str, help="出力先のファイルパス")

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    AnnotationSpecsDiffCommand(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "diff"
    subcommand_help = "アノテーション仕様の差分を出力します。"
    description = "アノテーション仕様の差分を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
