from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Literal, cast

import annofabcli.common.cli
from annofabcli.annotation_specs.diff_compare import create_annotation_specs_diff
from annofabcli.annotation_specs.diff_models import AnnotationSpecsDiffOutputFormat
from annofabcli.annotation_specs.diff_text_formatter import format_annotation_specs_diff_as_text
from annofabcli.annotation_specs.history import add_history_arguments, resolve_history_id_or_exit
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade
from annofabcli.common.utils import output_string, print_json

logger = logging.getLogger(__name__)

TargetName = Literal["labels", "attributes", "attribute_restrictions", "inspection_phrases", "metadata", "option"]
"""アノテーション仕様差分の出力対象。"""


def _add_annotation_specs_source_arguments(parser: argparse.ArgumentParser, *, prefix: str) -> None:
    source_group = parser.add_argument_group(f"{prefix} side")
    required_group = source_group.add_mutually_exclusive_group(required=True)
    required_group.add_argument(
        f"--{prefix}_project_id",
        help="比較対象のプロジェクトのproject_idを指定します。APIで取得したアノテーション仕様情報を元に比較します。",
    )
    required_group.add_argument(
        f"--{prefix}_annotation_specs_json_file",
        type=Path,
        help="比較対象のアノテーション仕様JSONを指定します。JSONファイルに記載された情報を元に比較します。",
    )

    add_history_arguments(source_group, prefix=f"{prefix}_")


class AnnotationSpecsDiffCommand(CommandLine):
    """アノテーション仕様の差分を出力する。"""

    COMMON_MESSAGE = "annofabcli annotation_specs diff: error:"

    def get_annotation_specs_from_source(self, *, prefix: str) -> dict[str, Any]:
        project_id = getattr(self.args, f"{prefix}_project_id")
        annotation_specs_json_file = getattr(self.args, f"{prefix}_annotation_specs_json_file")
        history_id = getattr(self.args, f"{prefix}_history_id")
        before = getattr(self.args, f"{prefix}_before")
        updated_datetime = getattr(self.args, f"{prefix}_updated_datetime")

        if annotation_specs_json_file is not None:
            if history_id is not None or before is not None or updated_datetime is not None:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --{prefix}_history_id/--{prefix}_before/--{prefix}_updated_datetime: '--{prefix}_annotation_specs_json_file' を指定したときは指定できません。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

            with annotation_specs_json_file.open(encoding="utf-8") as f:
                return json.load(f)

        assert project_id is not None
        resolved_history_id = resolve_history_id_or_exit(
            self.service,
            project_id,
            history_id=history_id,
            before=before,
            updated_datetime=updated_datetime,
            common_message=self.COMMON_MESSAGE,
            option_prefix=f"{prefix}_",
        )

        query_params = {"v": "3"}
        if resolved_history_id is not None:
            query_params["history_id"] = resolved_history_id
        annotation_specs, _ = self.service.api.get_annotation_specs(project_id, query_params=query_params)
        return annotation_specs

    def output_text(self, text: str) -> None:
        """差分テキストを出力する。

        空文字の場合は差分がない旨をログに出力する。
        標準出力の場合は、空文字なら何も出力しない。

        Args:
            text: 出力する差分テキスト。
        """
        if text == "":
            logger.info("差分はありません。")
        if self.args.output is None and text == "":
            return
        output_string(text, self.args.output)

    def main(self) -> None:
        left_specs = self.get_annotation_specs_from_source(prefix="left")
        right_specs = self.get_annotation_specs_from_source(prefix="right")
        targets: set[TargetName] = (
            set(cast(list[TargetName], self.args.target)) if self.args.target is not None else {"labels", "attributes", "attribute_restrictions", "inspection_phrases", "metadata", "option"}
        )
        diff = create_annotation_specs_diff(left_specs, right_specs, targets=targets)
        output_format = AnnotationSpecsDiffOutputFormat(self.args.format)

        if output_format == AnnotationSpecsDiffOutputFormat.TEXT:
            self.output_text(format_annotation_specs_diff_as_text(diff, left_specs=left_specs, right_specs=right_specs, detail=False))
            return

        if output_format == AnnotationSpecsDiffOutputFormat.DETAIL_TEXT:
            self.output_text(format_annotation_specs_diff_as_text(diff, left_specs=left_specs, right_specs=right_specs, detail=True))
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
        choices=["labels", "attributes", "attribute_restrictions", "inspection_phrases", "metadata", "option"],
        help="出力対象の差分を指定します。指定しない場合はすべて出力します。",
    )
    parser.add_argument(
        "-f",
        "--format",
        type=str,
        choices=[e.value for e in AnnotationSpecsDiffOutputFormat],
        default=AnnotationSpecsDiffOutputFormat.TEXT.value,
        help=(
            "出力フォーマット\n\n"
            "* text: 差分項目のみをセクション見出し付きの階層形式で表示する\n"
            "* detail_text: 差分項目と比較元・比較先の値をchanges配下のleft/right形式で表示する\n"
            "* json: 差分情報をJSONで出力する\n"
            "* pretty_json: 差分情報を整形JSONで出力する\n"
        ),
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
