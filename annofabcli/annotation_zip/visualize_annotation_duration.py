from __future__ import annotations

import argparse
import logging
import math
import tempfile
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

from annofabapi.models import DefaultAnnotationType, InputDataType, ProjectMemberRole

import annofabcli.common.cli
from annofabcli.annotation_zip.annotation_name import AnnotationNameTranslator, add_use_japanese_name_argument
from annofabcli.annotation_zip.count_annotation import add_attribute_value_arguments, add_label_name_argument
from annofabcli.common.annotation_count import AnnotationSpecs
from annofabcli.common.annotation_duration import AnnotationDuration, AttributeValueKey, ListAnnotationDurationByInputData
from annofabcli.common.annotation_duration_histogram import (
    TimeUnit,
    plot_annotation_duration_histogram_by_attribute,
    plot_annotation_duration_histogram_by_label,
)
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery

logger = logging.getLogger(__name__)


@dataclass
class DurationPlotData:
    """ヒストグラム用の長さ情報と表示順。"""

    durations: list[AnnotationDuration]
    """タスクごとの区間アノテーションの長さ。"""
    label_keys: list[str]
    """ラベルの表示順。"""
    attribute_keys: list[AttributeValueKey]
    """属性値の表示順。"""


def get_duration_plot_data(
    annotation_path: Path,
    specs: AnnotationSpecs,
    args: argparse.Namespace,
    translator: AnnotationNameTranslator | None = None,
) -> DurationPlotData:
    """対象の名称を絞り込み、日本語名へ変換した描画データを作ります。

    Args:
        annotation_path: ZIPまたは展開済みディレクトリ。
        specs: 区間アノテーションの仕様。
        args: コマンドライン引数。
        translator: 日本語名への変換。

    Returns:
        描画データと表示順。
    """
    labels = specs.label_keys()
    if args.label_name is not None:
        labels, unknown = specs.get_label_keys_by_label_names(annofabcli.common.cli.get_list_from_args(args.label_name))
        if unknown:
            logger.warning(f"アノテーション仕様にないラベル名: {unknown}")
    attributes = specs.selective_attribute_name_keys()
    if args.by_attribute:
        names = args.attribute_name if args.attribute_name is not None else args.additional_attribute_name
        if names is not None:
            specified, unknown = specs.get_attribute_name_keys_by_attribute_names(annofabcli.common.cli.get_list_from_args(names))
            if unknown:
                logger.warning(f"アノテーション仕様にない属性名: {unknown}")
            attributes = specified if args.attribute_name is not None else list(dict.fromkeys([*attributes, *specified]))
    attributes = [key for key in attributes if key[0] in labels]
    durations = ListAnnotationDurationByInputData(
        target_labels=labels if args.label_name is not None else None,
        target_attribute_names=attributes,
    ).get_annotation_duration_list(
        annotation_path,
        target_task_ids=annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None,
        task_query=TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None,
    )
    if len({(e.project_id, e.task_id) for e in durations}) != len(durations):
        raise AnnofabCliException("入力データが複数あるタスクが含まれています。動画タスクを指定してください。")
    attribute_keys = list(
        dict.fromkeys(
            [
                *specs.get_attribute_value_keys_for_target_attributes(attributes),
                *sorted({key for duration in durations for key in duration.annotation_duration_second_by_attribute}),
            ]
        )
    )
    if translator is not None:
        translated = []
        for duration in durations:
            label_values: dict[str, float] = defaultdict(float)
            attribute_values: dict[AttributeValueKey, float] = defaultdict(float)
            for label, value in duration.annotation_duration_second_by_label.items():
                label_values[translator.label_name(label)] += value
            for key, value in duration.annotation_duration_second_by_attribute.items():
                attribute_values[translator.attribute_value_key(key)] += value
            translated.append(replace(duration, annotation_duration_second_by_label=dict(label_values), annotation_duration_second_by_attribute=dict(attribute_values)))
        durations = translated
        labels = list(dict.fromkeys(translator.label_name(label) for label in labels))
        attribute_keys = list(dict.fromkeys(translator.attribute_value_key(key) for key in attribute_keys))
    return DurationPlotData(durations, labels, attribute_keys)


class VisualizeAnnotationDuration(CommandLine):
    """タスクごとの区間アノテーションの長さを可視化します。"""

    def main(self) -> None:
        """必要な入力を取得し、HTMLファイルを出力します。

        Args:
            なし。

        Returns:
            None。
        """
        args = self.args
        self.require_project_access(args.project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        project, _ = self.service.api.get_project(args.project_id)
        if project["input_data_type"] != InputDataType.MOVIE.value:
            raise AnnofabCliException("動画プロジェクトを指定してください。")
        specs = AnnotationSpecs(self.service, args.project_id, annotation_type=DefaultAnnotationType.RANGE.value)
        translator = AnnotationNameTranslator.from_project(self.service, args.project_id) if args.use_japanese_name else None
        with tempfile.TemporaryDirectory() as directory:
            annotation_path = args.annotation
            if annotation_path is None:
                annotation_path = DownloadingFile(self.service).download_annotation_zip_to_dir(args.project_id, args.temp_dir if args.temp_dir is not None else Path(directory), is_latest=args.latest)
            data = get_duration_plot_data(annotation_path, specs, args, translator)
        metadata = {
            "project_id": args.project_id,
            "project_title": project["title"],
            "task_query": annofabcli.common.cli.get_json_from_args(args.task_query) if args.task_query is not None else None,
            "target_task_ids": annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None,
        }
        logger.info(f"{len(data.durations)}件のタスクの区間アノテーションの長さを可視化します。")
        if args.by_attribute:
            plot_annotation_duration_histogram_by_attribute(
                data.durations,
                output_file=Path(args.output),
                time_unit=TimeUnit(args.time_unit),
                bin_width=args.bin_width,
                prior_keys=data.attribute_keys,
                exclude_empty_value=args.exclude_empty_value,
                arrange_bin_edge=args.arrange_bin_edge,
                metadata=metadata,
            )
        else:
            plot_annotation_duration_histogram_by_label(
                data.durations,
                output_file=Path(args.output),
                time_unit=TimeUnit(args.time_unit),
                bin_width=args.bin_width,
                prior_keys=data.label_keys,
                exclude_empty_value=args.exclude_empty_value,
                arrange_bin_edge=args.arrange_bin_edge,
                metadata=metadata,
            )


def main(args: argparse.Namespace) -> None:
    """ビン幅を検証して可視化コマンドを実行します。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    if args.bin_width is not None and (not math.isfinite(args.bin_width) or args.bin_width <= 0):
        raise AnnofabCliException("--bin_widthには正の有限な秒数を指定してください。")
    service = build_annofabapi_resource_and_login(args)
    VisualizeAnnotationDuration(service, AnnofabApiFacade(service), args).main()


def add_arguments(parser: argparse.ArgumentParser, *, by_attribute: bool) -> None:
    """区間長の可視化コマンドの引数を登録します。

    Args:
        parser: 引数パーサー。
        by_attribute: 属性値ごとの可視化か。

    Returns:
        None。
    """
    arguments = ArgumentParser(parser)
    arguments.add_project_id()
    parser.add_argument("--annotation", type=Path, help="アノテーションZIPまたは展開済みディレクトリ。省略するとダウンロードします。")
    arguments.add_output(required=True, help_message="出力先HTMLファイルのパスを指定します。")
    parser.add_argument("--time_unit", choices=[e.value for e in TimeUnit], default=TimeUnit.SECOND.value, help="ヒストグラムに表示する時間の単位。")
    parser.add_argument("--bin_width", type=float, help="ビンの幅を正の秒数で指定します。表示単位が分でも秒で指定します。省略するとビンの個数が20になるように調整します。")
    parser.add_argument("--exclude_empty_value", action="store_true", help="すべてのタスクで区間長が0のヒストグラムを描画しません。")
    parser.add_argument("--arrange_bin_edge", action="store_true", help="各ヒストグラムの範囲とビン幅をそろえます。")
    arguments.add_task_id(required=False)
    parser.add_argument("--task_query", "-tq", help="対象タスクの条件をJSONで指定します。キーはtask_id, status, phase, phase_stageです。file://でファイルを指定できます。")
    parser.add_argument("--latest", action="store_true", help="ZIPのダウンロード時に最新のアノテーションZIPを取得します。数分待つ場合があります。")
    parser.add_argument("--temp_dir", type=Path, help="アノテーションZIPのダウンロード先ディレクトリ。")
    add_use_japanese_name_argument(parser)
    if by_attribute:
        add_attribute_value_arguments(parser)
    else:
        add_label_name_argument(parser, target_description="区間アノテーション")
    parser.set_defaults(subcommand_func=main, by_attribute=by_attribute)
