from __future__ import annotations

import argparse
import json
import logging
import tempfile
from collections import defaultdict
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import DefaultAnnotationType, InputDataType, ProjectMemberRole

from annofabcli.annotation_zip.annotation_name import AnnotationNameTranslator, add_use_japanese_name_argument
from annofabcli.annotation_zip.count_aggregation import is_summary_group, validate_group_by
from annofabcli.annotation_zip.count_annotation import add_attribute_value_arguments, add_label_name_argument
from annofabcli.common.annofab.annotation_zip import lazy_parse_simple_annotation_by_input_data
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_json_from_args, get_list_from_args
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery, match_annotation_with_task_query
from annofabcli.common.utils import print_csv, print_json
from annofabcli.statistics.list_annotation_count import AnnotationSpecs

logger = logging.getLogger(__name__)
AttributeKey = tuple[str, str, str]
"""ラベル名、属性名、属性値の組。"""


@dataclass
class DurationOptions:
    """長さ集計の対象と出力設定。"""

    group_by: list[str] = field(default_factory=lambda: ["task_id"])
    label_names: Collection[str] | None = None
    attribute_names: Collection[tuple[str, str]] = ()
    task_ids: Collection[str] | None = None
    task_query: TaskQuery | None = None
    with_task_metadata: bool = False


@dataclass
class DurationSummary:
    """集計キーごとの区間長と動画長。"""

    info: dict[str, Any]
    video_duration_second: float | None = 0.0
    labels: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    attributes: dict[AttributeKey, float] = field(default_factory=lambda: defaultdict(float))
    task_keys: set[tuple[str, str]] = field(default_factory=set)
    input_data_count: int = 0


def aggregate_annotation_durations(
    annotations: Collection[Mapping[str, Any]],
    input_data_list: Collection[Mapping[str, Any]],
    task_list: Collection[Mapping[str, Any]],
    options: DurationOptions,
) -> list[DurationSummary]:
    """ZIP由来の入力データごとの情報を集計します。

    Args:
        annotations: simple形式のアノテーションJSON一覧。
        input_data_list: 動画長取得用の入力データ一覧。
        task_list: メタデータ取得用のタスク一覧。
        options: 集計設定。

    Returns:
        区間長と動画長の集計結果。動画長が不明な入力を含む場合はNone。
    """
    data_by_id = {data["input_data_id"]: data for data in input_data_list}
    task_by_id = {task["task_id"]: task for task in task_list}
    summaries: dict[tuple[tuple[type, str], ...], DurationSummary] = {}
    for annotation in annotations:
        task_id = annotation["task_id"]
        if options.task_ids is not None and task_id not in options.task_ids:
            continue
        if options.task_query is not None and not match_annotation_with_task_query(dict(annotation), options.task_query):
            continue
        task = task_by_id.get(task_id, {})
        if "input_data_id_list" in task and len(task["input_data_id_list"]) != 1:
            raise ValueError(f"task_id='{task_id}'の入力データ数が1ではありません。動画タスクを指定してください。")
        info = get_group_info(annotation, task, options)
        if is_summary_group(options.group_by):
            key_fields = info
        else:
            key_fields = {"project_id": annotation["project_id"], "task_id": task_id}
        key = tuple((type(value), json.dumps(value, ensure_ascii=False, sort_keys=True)) for value in key_fields.values())
        summary = summaries.setdefault(key, DurationSummary(info=info))
        summary.task_keys.add((annotation["project_id"], task_id))
        summary.input_data_count += 1
        data = data_by_id.get(annotation["input_data_id"], {})
        video_duration = data.get("system_metadata", {}).get("input_duration")
        if video_duration is None:
            logger.warning(f"task_id='{task_id}', input_data_id='{annotation['input_data_id']}'の動画長を取得できません。")
            summary.video_duration_second = None
        elif summary.video_duration_second is not None:
            summary.video_duration_second += video_duration
        for detail in annotation["details"]:
            label = detail["label"]
            if detail["data"]["_type"] != "Range" or (options.label_names is not None and label not in options.label_names):
                continue
            duration = (detail["data"]["end"] - detail["data"]["begin"]) / 1000
            summary.labels[label] += duration
            for name, value in detail["attributes"].items():
                if (label, name) in options.attribute_names:
                    value_key = str(value).lower() if isinstance(value, bool) else str(value)
                    summary.attributes[(label, name, value_key)] += duration
    return list(summaries.values())


def get_group_info(annotation: Mapping[str, Any], task: Mapping[str, Any], options: DurationOptions) -> dict[str, Any]:
    """出力する集計キーと識別情報を取得します。

    Args:
        annotation: 入力データのアノテーション。
        task: タスク情報。
        options: 集計設定。

    Returns:
        識別情報。
    """
    if is_summary_group(options.group_by):
        info = {}
        for name in options.group_by:
            if name.startswith("task_metadata."):
                value = task.get("metadata", {}).get(name.removeprefix("task_metadata."))
                if value is not None and not isinstance(value, str | int | float | bool):
                    value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            else:
                value = annotation[name]
            info[name] = value
        return info
    info = {name: annotation[name] for name in ["project_id", "task_id", "task_phase", "task_phase_stage", "task_status", "input_data_id", "input_data_name", "updated_datetime"]}
    if options.with_task_metadata:
        info["task_metadata"] = task.get("metadata", {})
    return info


def make_output_rows(
    summaries: Collection[DurationSummary],
    options: DurationOptions,
    *,
    by_attribute: bool,
    label_columns: Collection[str],
    attribute_columns: Collection[AttributeKey],
    translator: AnnotationNameTranslator | None = None,
) -> list[dict[str, Any]]:
    """仕様で定義された未出現値を0秒で補い、出力用辞書を作ります。

    Args:
        summaries: 集計結果。
        options: 集計設定。
        by_attribute: 属性値ごとの出力か。
        label_columns: 仕様上の対象ラベル。
        attribute_columns: 仕様上の対象属性値。
        translator: 日本語名への変換。

    Returns:
        JSONとCSV出力用の辞書一覧。
    """
    rows = []
    for summary in summaries:
        row = {**summary.info, "video_duration_second": summary.video_duration_second}
        if is_summary_group(options.group_by):
            row["task_count"] = len(summary.task_keys)
            row["input_data_count"] = summary.input_data_count
        if by_attribute:
            values: dict[AttributeKey, float] = defaultdict(float)
            for key in dict.fromkeys([*attribute_columns, *summary.attributes]):
                output_key = translator.attribute_value_key(key) if translator is not None else key
                values[output_key] += summary.attributes.get(key, 0.0)
            nested: dict[str, dict[str, dict[str, float]]] = {}
            for (label, name, value), duration in values.items():
                nested.setdefault(label, {}).setdefault(name, {})[value] = duration
            row["annotation_duration_second_by_attribute_value"] = nested
        else:
            labels: dict[str, float] = defaultdict(float)
            for label in dict.fromkeys([*label_columns, *summary.labels]):
                output_label = translator.label_name(label) if translator is not None else label
                labels[output_label] += summary.labels.get(label, 0.0)
            row["annotation_duration_second"] = sum(labels.values())
            row["annotation_duration_second_by_label"] = dict(labels)
        rows.append(row)
    return rows


def create_duration_dataframe(rows: Collection[dict[str, Any]], base_columns: Collection[str], value_columns: Collection, *, by_attribute: bool) -> pandas.DataFrame:
    """横持ちCSVを作ります。属性値の場合は3行ヘッダーです。

    Args:
        rows: 出力用辞書。
        base_columns: 識別情報の列。
        value_columns: 仕様上のラベルまたは属性値列。
        by_attribute: 属性値ごとの出力か。

    Returns:
        0件でもヘッダーを持つDataFrame。
    """
    flat_rows = []
    columns = list(value_columns)
    for row in rows:
        flat = {key: value for key, value in row.items() if not key.startswith("annotation_duration_second_by_") and key != "task_metadata"}
        flat.update({f"task_metadata.{key}": value for key, value in row.get("task_metadata", {}).items()})
        if by_attribute:
            values = {
                (label, name, value): duration for label, names in row["annotation_duration_second_by_attribute_value"].items() for name, values in names.items() for value, duration in values.items()
            }
        else:
            values = row["annotation_duration_second_by_label"]
        columns.extend(key for key in values if key not in columns)
        csv_row: dict[str | AttributeKey, Any] = {}
        for name, value in flat.items():
            csv_row[(name, "", "") if by_attribute else name] = value
        csv_row.update(values.items())
        flat_rows.append(csv_row)
    basic = [(key, "", "") for key in base_columns] if by_attribute else list(base_columns)
    output_columns = [*basic, *columns]
    df = pandas.DataFrame(flat_rows, columns=pandas.MultiIndex.from_tuples(output_columns) if by_attribute else output_columns)
    return df.fillna(dict.fromkeys(columns, 0.0))


class SumAnnotationDuration(CommandLine):
    """区間アノテーションの長さを出力するコマンド。"""

    def run(self, *, by_attribute: bool) -> None:
        """入力を取得して集計結果を出力します。

        Args:
            by_attribute: 属性値ごとの集計か。

        Returns:
            None。
        """
        args = self.args
        self.require_project_access(args.project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        project, _ = self.service.api.get_project(args.project_id)
        if project["input_data_type"] != InputDataType.MOVIE.value:
            raise AnnofabCliException("動画プロジェクトを指定してください。")
        specs = AnnotationSpecs(self.service, args.project_id, annotation_type=DefaultAnnotationType.RANGE.value)
        labels = specs.label_keys()
        if args.label_name is not None:
            labels, unknown = specs.get_label_keys_by_label_names(get_list_from_args(args.label_name))
            if unknown:
                logger.warning(f"アノテーション仕様にないラベル名: {unknown}")
        attributes = self.get_attribute_names(specs, labels, by_attribute=by_attribute)
        options = DurationOptions(
            group_by=args.group_by,
            label_names=labels if args.label_name is not None else None,
            attribute_names=attributes,
            task_ids=get_list_from_args(args.task_id) if args.task_id is not None else None,
            task_query=TaskQuery.from_dict(get_json_from_args(args.task_query)) if args.task_query is not None else None,
            with_task_metadata=args.with_task_metadata,
        )
        translator = AnnotationNameTranslator.from_project(self.service, args.project_id) if args.use_japanese_name else None
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = args.temp_dir if args.temp_dir is not None else Path(directory)
            downloading = DownloadingFile(self.service)
            annotation_path = args.annotation
            if annotation_path is None:
                annotation_path = downloading.download_annotation_zip_to_dir(args.project_id, temp_dir, is_latest=args.latest)
            input_path = downloading.download_input_data_json_to_dir(args.project_id, temp_dir, is_latest=args.latest)
            task_path = downloading.download_task_json_to_dir(args.project_id, temp_dir, is_latest=args.latest)
            with input_path.open(encoding="utf-8") as file:
                input_data_list = json.load(file)
            with task_path.open(encoding="utf-8") as file:
                task_list = json.load(file)
            annotations = []
            for index, parser in enumerate(lazy_parse_simple_annotation_by_input_data(annotation_path)):
                if (index + 1) % 1000 == 0:
                    logger.info(f"{index + 1}件のアノテーションJSONを読み込みました。")
                annotations.append(parser.load_json())
            summaries = aggregate_annotation_durations(annotations, input_data_list, task_list, options)
        attribute_columns = specs.get_attribute_value_keys_for_target_attributes(attributes)
        rows = make_output_rows(summaries, options, by_attribute=by_attribute, label_columns=labels, attribute_columns=attribute_columns, translator=translator)
        logger.info(f"{len(annotations)}件の入力データから{len(rows)}件の集計結果を出力します。")
        if OutputFormat(args.format) != OutputFormat.CSV:
            print_json(rows, is_pretty=args.format == OutputFormat.PRETTY_JSON.value, output=args.output)
            return
        base_columns = get_output_columns(options, task_list)
        if not by_attribute:
            base_columns.append("annotation_duration_second")
        if by_attribute:
            value_columns: Collection = [translator.attribute_value_key(key) if translator is not None else key for key in attribute_columns]
        else:
            value_columns = [translator.label_name(label) if translator is not None else label for label in labels]
        df = create_duration_dataframe(rows, base_columns, list(dict.fromkeys(value_columns)), by_attribute=by_attribute)
        print_csv(df, args.output)

    def get_attribute_names(self, specs: AnnotationSpecs, labels: Collection[str], *, by_attribute: bool) -> list[tuple[str, str]]:
        """属性名指定と対象ラベルから集計属性を決定します。

        Args:
            specs: 区間アノテーションの仕様。
            labels: 対象ラベル。
            by_attribute: 属性値集計用か。

        Returns:
            対象ラベルと属性名の組。
        """
        attributes = specs.selective_attribute_name_keys()
        if by_attribute:
            args = self.args
            names = args.attribute_name if args.attribute_name is not None else args.additional_attribute_name
            if names is not None:
                specified, unknown = specs.get_attribute_name_keys_by_attribute_names(get_list_from_args(names))
                if unknown:
                    logger.warning(f"アノテーション仕様にない属性名: {unknown}")
                attributes = specified if args.attribute_name is not None else list(dict.fromkeys([*attributes, *specified]))
        return [key for key in attributes if key[0] in labels]


def get_output_columns(options: DurationOptions, task_list: Collection[Mapping[str, Any]]) -> list[str]:
    """空の結果にも適用するCSV列を返します。

    Args:
        options: 集計設定。
        task_list: メタデータ列取得用のタスク一覧。

    Returns:
        基本列の一覧。
    """
    if is_summary_group(options.group_by):
        return [*options.group_by, "task_count", "input_data_count", "video_duration_second"]
    columns = ["project_id", "task_id", "task_phase", "task_phase_stage", "task_status", "input_data_id", "input_data_name", "updated_datetime"]
    if options.with_task_metadata:
        columns.extend(f"task_metadata.{key}" for key in sorted({key for task in task_list for key in task.get("metadata", {})}))
    return [*columns, "video_duration_second"]


def add_arguments(parser: argparse.ArgumentParser, *, by_attribute: bool) -> None:
    """長さ集計コマンドのオプションを登録します。

    Args:
        parser: 引数パーサー。
        by_attribute: 属性値集計用か。

    Returns:
        None。
    """
    arguments = ArgumentParser(parser)
    arguments.add_project_id()
    parser.add_argument("--annotation", type=Path, help="アノテーションZIPまたは展開済みディレクトリ。省略するとダウンロードします。")
    parser.add_argument("--group_by", nargs="+", default=["task_id"], help="集計単位。task_id, project_id, task_phase, task_phase_stage, task_status, task_metadata.<key>を指定できます。")
    arguments.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    arguments.add_output()
    arguments.add_task_id(required=False)
    parser.add_argument("--task_query", "-tq", help="対象タスクの条件をJSONで指定します。キーはtask_id, status, phase, phase_stageです。file://でファイルを指定できます。")
    parser.add_argument("--latest", action="store_true", help="最新のアノテーションZIP、入力データ、タスク情報を取得します。数分待つ場合があります。")
    parser.add_argument("--temp_dir", type=Path, help="ダウンロード先ディレクトリ。")
    parser.add_argument("--with_task_metadata", action="store_true", help="タスク単位の出力にタスクメタデータを追加します。")
    add_use_japanese_name_argument(parser)
    if by_attribute:
        add_attribute_value_arguments(parser)
    else:
        add_label_name_argument(parser, target_description="区間アノテーション")
    parser.set_defaults(subcommand_func=main_attribute if by_attribute else main_label)


def run_command(args: argparse.Namespace, *, by_attribute: bool) -> None:
    """オプションの組み合わせを検証してコマンドを実行します。

    Args:
        args: コマンドライン引数。
        by_attribute: 属性値集計用か。

    Returns:
        None。
    """
    if "input_data_id" in args.group_by:
        raise AnnofabCliException("動画タスクには入力データが1個しか含まれないため、--group_by task_idを指定してください。")
    error = validate_group_by(args.group_by)
    if error is not None:
        raise AnnofabCliException(error)
    if args.with_task_metadata and is_summary_group(args.group_by):
        raise AnnofabCliException("--with_task_metadataはタスク単位の出力で指定してください。")
    service = build_annofabapi_resource_and_login(args)
    SumAnnotationDuration(service, AnnofabApiFacade(service), args).run(by_attribute=by_attribute)


def main_label(args: argparse.Namespace) -> None:
    """ラベル別の長さ集計を実行します。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    run_command(args, by_attribute=False)


def main_attribute(args: argparse.Namespace) -> None:
    """属性値別の長さ集計を実行します。

    Args:
        args: コマンドライン引数。

    Returns:
        None。
    """
    run_command(args, by_attribute=True)
