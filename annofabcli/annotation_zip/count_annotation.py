from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from collections import Counter
from collections.abc import Collection, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import annofabapi
import pandas
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.annotation_zip.annotation_name import AnnotationNameTranslator, add_use_japanese_name_argument
from annofabcli.annotation_zip.count_aggregation import (
    INPUT_DATA_ID_GROUP,
    TASK_ID_GROUP,
    CountSummary,
    aggregate_task_counts,
    is_summary_group,
    needs_task_metadata,
    validate_group_by,
)
from annofabcli.annotation_zip.task_metadata import get_task_metadata_by_task_id, get_task_metadata_keys
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.common.utils import print_csv, print_json
from annofabcli.statistics.list_annotation_count import (
    AnnotationCounterByInputData,
    AnnotationCounterByTask,
    AnnotationSpecs,
    AttributeCountCsv,
    AttributeNameKey,
    AttributeValueKey,
    GroupBy,
    LabelCountCsv,
    ListAnnotationCounterByInputData,
    ListAnnotationCounterByTask,
    ListAnnotationCountMain,
    encode_annotation_count_by_attribute,
)

logger = logging.getLogger(__name__)


class CountTarget:
    """集計対象を表す定数。"""

    LABEL = "label"
    """ラベルごとのアノテーション数"""

    ATTRIBUTE_VALUE = "attribute_value"
    """属性値ごとのアノテーション数"""


class CountAnnotationMain:
    def __init__(self, annotation_specs: AnnotationSpecs, name_translator: AnnotationNameTranslator | None = None) -> None:
        """
        Args:
            annotation_specs: アノテーション仕様
            name_translator: 出力する名称の変換オブジェクト。
        """
        self.annotation_specs = annotation_specs
        self.name_translator = name_translator

    def _translate_counter(self, counter: AnnotationCounterByTask | AnnotationCounterByInputData) -> AnnotationCounterByTask | AnnotationCounterByInputData:
        """集計結果の名称を日本語名へ変換します。

        Args:
            counter: 名称を変換する集計結果。

        Returns:
            名称を変換した集計結果。
        """
        if self.name_translator is None:
            return counter

        annotation_count_by_label: Counter[str] = Counter()
        for label_name, count in counter.annotation_count_by_label.items():
            annotation_count_by_label[self.name_translator.label_name(label_name)] += count

        annotation_count_by_attribute: Counter[tuple[str, str, str]] = Counter()
        for key, count in counter.annotation_count_by_attribute.items():
            annotation_count_by_attribute[self.name_translator.attribute_value_key(key)] += count
        return replace(
            counter,
            annotation_count_by_label=annotation_count_by_label,
            annotation_count_by_attribute=annotation_count_by_attribute,
        )

    @staticmethod
    def _target_attribute_names_only(
        annotation_specs: AnnotationSpecs,
        additional_attribute_names: Collection[AttributeNameKey] | None,
        specified_attribute_names: Collection[AttributeNameKey] | None,
    ) -> list[str]:
        if specified_attribute_names is not None:
            return list({attr_name for _, attr_name in specified_attribute_names})

        default_selective_attributes = annotation_specs.selective_attribute_name_keys()
        default_attribute_names = {attr_name for _, attr_name in default_selective_attributes}
        if additional_attribute_names is not None:
            additional_attr_names = {attr_name for _, attr_name in additional_attribute_names}
            return list(default_attribute_names | additional_attr_names)

        return list(default_attribute_names)

    def get_counter_list(
        self,
        annotation_path: Path,
        group_by: GroupBy,
        *,
        task_json_path: Path | None = None,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
        target_label_names: Collection[str] | None = None,
        additional_attribute_names: Collection[AttributeNameKey] | None = None,
        specified_attribute_names: Collection[AttributeNameKey] | None = None,
    ) -> list[AnnotationCounterByTask] | list[AnnotationCounterByInputData]:
        """
        アノテーションZIPからアノテーション数を集計します。

        Args:
            annotation_path: アノテーションzipまたはzipを展開したディレクトリのパス
            group_by: 集計単位
            task_json_path: タスクJSONファイルのパス。フレーム番号を出力する場合に指定します。
            target_task_ids: 集計対象のタスクID
            task_query: 集計対象タスクを絞り込むためのクエリ条件
            additional_attribute_names: デフォルトの選択系属性に加えて集計対象とする属性名
            specified_attribute_names: 集計対象とする属性名

        Returns:
            アノテーション数の集計結果
        """
        target_attribute_names_only = self._target_attribute_names_only(
            self.annotation_specs,
            additional_attribute_names=additional_attribute_names,
            specified_attribute_names=specified_attribute_names,
        )
        if group_by == GroupBy.INPUT_DATA_ID:
            frame_no_map = ListAnnotationCountMain.get_frame_no_map(task_json_path) if task_json_path is not None else None
            input_data_result = ListAnnotationCounterByInputData(
                target_labels=target_label_names,
                target_attribute_names_only=target_attribute_names_only,
                frame_no_map=frame_no_map,
            ).get_annotation_counter_list(
                annotation_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
            )
            return [cast(AnnotationCounterByInputData, self._translate_counter(e)) for e in input_data_result]

        task_result = ListAnnotationCounterByTask(
            target_labels=target_label_names,
            target_attribute_names_only=target_attribute_names_only,
        ).get_annotation_counter_list(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )
        return [cast(AnnotationCounterByTask, self._translate_counter(e)) for e in task_result]

    def iter_task_counter(
        self,
        annotation_path: Path,
        *,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
        target_label_names: Collection[str] | None = None,
        additional_attribute_names: Collection[AttributeNameKey] | None = None,
        specified_attribute_names: Collection[AttributeNameKey] | None = None,
    ) -> Iterator[AnnotationCounterByTask]:
        """タスク単位のアノテーション数を順次返します。

        Args:
            annotation_path: アノテーションzipまたは展開したディレクトリ。
            target_task_ids: 集計対象のタスクID。
            task_query: 集計対象タスクの絞り込み条件。
            target_label_names: 集計対象のラベル名。
            additional_attribute_names: 追加で集計する属性名。
            specified_attribute_names: 集計対象とする属性名。

        Yields:
            タスク単位のアノテーション数。
        """
        target_attribute_names_only = self._target_attribute_names_only(
            self.annotation_specs,
            additional_attribute_names=additional_attribute_names,
            specified_attribute_names=specified_attribute_names,
        )
        counter = ListAnnotationCounterByTask(
            target_labels=target_label_names,
            target_attribute_names_only=target_attribute_names_only,
        )
        for result in counter.iter_annotation_counter(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        ):
            yield cast(AnnotationCounterByTask, self._translate_counter(result))

    def print_label_count(  # noqa: PLR0913
        self,
        annotation_path: Path,
        group_by: list[str],
        output_file: Path,
        arg_format: OutputFormat,
        *,
        task_json_path: Path | None = None,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
        target_label_names: Collection[str] | None = None,
        with_per_input_data: bool = False,
        task_metadata_keys: Collection[str] | None = None,
        task_metadata_by_task_id: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """
        ラベルごとのアノテーション数を出力します。
        """
        if is_summary_group(group_by):
            summaries = aggregate_task_counts(
                self.iter_task_counter(
                    annotation_path,
                    target_task_ids=target_task_ids,
                    task_query=task_query,
                    target_label_names=target_label_names,
                ),
                group_by,
                value_counts_getter=lambda count: count.annotation_count_by_label,
                annotation_count_getter=lambda count: count.annotation_count,
                task_metadata_by_task_id=task_metadata_by_task_id,
            )
            logger.info(f"{sum(summary.task_count for summary in summaries)} 件のタスクを {len(summaries)} グループに集計しました。")
            label_columns = list(target_label_names) if target_label_names is not None else self.annotation_specs.label_keys()
            if self.name_translator is not None:
                label_columns = [self.name_translator.label_name(value) for value in label_columns]
            self._print_label_summaries(summaries, group_by, output_file, arg_format, label_columns)
            return

        detail_group_by = GroupBy(group_by[0])
        counter_list: list[AnnotationCounterByTask | AnnotationCounterByInputData] = [
            *self.get_counter_list(
                annotation_path,
                detail_group_by,
                task_json_path=task_json_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
                target_label_names=target_label_names,
            )
        ]
        if task_metadata_by_task_id is not None:
            counter_list = [replace(counter, task_metadata=task_metadata_by_task_id.get(counter.task_id, {})) for counter in counter_list]
        if arg_format == OutputFormat.CSV:
            label_columns = list(target_label_names) if target_label_names is not None else self.annotation_specs.label_keys()
            if self.name_translator is not None:
                label_columns = [self.name_translator.label_name(e) for e in label_columns]
            if detail_group_by == GroupBy.INPUT_DATA_ID:
                LabelCountCsv().print_csv_by_input_data(
                    cast(list[AnnotationCounterByInputData], counter_list),
                    output_file,
                    prior_label_columns=label_columns,
                    task_metadata_keys=task_metadata_keys,
                )
            else:
                LabelCountCsv().print_csv_by_task(
                    cast(list[AnnotationCounterByTask], counter_list),
                    output_file,
                    prior_label_columns=label_columns,
                    with_per_input_data=with_per_input_data,
                    task_metadata_keys=task_metadata_keys,
                )
            return

        print_json(
            [self.to_label_count_dict(e) for e in counter_list],
            is_pretty=arg_format == OutputFormat.PRETTY_JSON,
            output=output_file,
        )

    def print_attribute_value_count(  # noqa: PLR0913
        self,
        annotation_path: Path,
        group_by: list[str],
        output_file: Path,
        arg_format: OutputFormat,
        *,
        task_json_path: Path | None = None,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
        target_label_names: Collection[str] | None = None,
        additional_attribute_names: Collection[AttributeNameKey] | None = None,
        specified_attribute_names: Collection[AttributeNameKey] | None = None,
        with_per_input_data: bool = False,
        task_metadata_keys: Collection[str] | None = None,
        task_metadata_by_task_id: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """
        属性値ごとのアノテーション数を出力します。
        """
        attribute_columns = self.attribute_value_columns(
            additional_attribute_names=additional_attribute_names,
            specified_attribute_names=specified_attribute_names,
            target_label_names=target_label_names,
        )
        if is_summary_group(group_by):
            summaries = aggregate_task_counts(
                self.iter_task_counter(
                    annotation_path,
                    target_task_ids=target_task_ids,
                    task_query=task_query,
                    target_label_names=target_label_names,
                    additional_attribute_names=additional_attribute_names,
                    specified_attribute_names=specified_attribute_names,
                ),
                group_by,
                value_counts_getter=lambda count: count.annotation_count_by_attribute,
                task_metadata_by_task_id=task_metadata_by_task_id,
            )
            logger.info(f"{sum(summary.task_count for summary in summaries)} 件のタスクを {len(summaries)} グループに集計しました。")
            self._print_attribute_value_summaries(summaries, group_by, output_file, arg_format, attribute_columns)
            return

        detail_group_by = GroupBy(group_by[0])
        counter_list: list[AnnotationCounterByTask | AnnotationCounterByInputData] = [
            *self.get_counter_list(
                annotation_path,
                detail_group_by,
                task_json_path=task_json_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
                target_label_names=target_label_names,
                additional_attribute_names=additional_attribute_names,
                specified_attribute_names=specified_attribute_names,
            )
        ]
        if task_metadata_by_task_id is not None:
            counter_list = [replace(counter, task_metadata=task_metadata_by_task_id.get(counter.task_id, {})) for counter in counter_list]
        if arg_format == OutputFormat.CSV:
            if detail_group_by == GroupBy.INPUT_DATA_ID:
                AttributeCountCsv().print_csv_by_input_data(
                    cast(list[AnnotationCounterByInputData], counter_list),
                    output_file,
                    prior_attribute_columns=attribute_columns,
                    with_annotation_count=False,
                    task_metadata_keys=task_metadata_keys,
                )
            else:
                AttributeCountCsv().print_csv_by_task(
                    cast(list[AnnotationCounterByTask], counter_list),
                    output_file,
                    prior_attribute_columns=attribute_columns,
                    with_per_input_data=with_per_input_data,
                    with_annotation_count=False,
                    task_metadata_keys=task_metadata_keys,
                )
            return

        print_json(
            [self.to_attribute_value_count_dict(e) for e in counter_list],
            is_pretty=arg_format == OutputFormat.PRETTY_JSON,
            output=output_file,
        )

    @staticmethod
    def _print_label_summaries(
        summaries: Collection[CountSummary],
        group_by: Collection[str],
        output_file: Path,
        arg_format: OutputFormat,
        label_columns: list[str],
    ) -> None:
        """ラベルごとのサマリーを出力します。

        Args:
            summaries: サマリー集計結果。
            group_by: 集計キー。
            output_file: 出力先。
            arg_format: 出力形式。
            label_columns: 出力するラベル列。
        """
        remaining_columns = sorted({cast(str, key) for summary in summaries for key in summary.value_counts} - set(label_columns))
        label_columns = [*label_columns, *remaining_columns]
        rows = [
            {
                **summary.group_values,
                "task_count": summary.task_count,
                "input_data_count": summary.input_data_count,
                "annotation_count": summary.annotation_count,
                **summary.value_counts,
            }
            for summary in summaries
        ]
        if arg_format == OutputFormat.CSV:
            columns = [*group_by, "task_count", "input_data_count", "annotation_count", *label_columns]
            df = pandas.DataFrame(rows, columns=columns)
            df = df.fillna(dict.fromkeys(label_columns, 0))
            print_csv(df, output=output_file)
            return

        json_rows = [
            {
                **summary.group_values,
                "task_count": summary.task_count,
                "input_data_count": summary.input_data_count,
                "annotation_count": summary.annotation_count,
                "annotation_count_by_label": dict(summary.value_counts),
            }
            for summary in summaries
        ]
        print_json(json_rows, is_pretty=arg_format == OutputFormat.PRETTY_JSON, output=output_file)

    @staticmethod
    def _print_attribute_value_summaries(
        summaries: Collection[CountSummary],
        group_by: Collection[str],
        output_file: Path,
        arg_format: OutputFormat,
        attribute_columns: list[AttributeValueKey],
    ) -> None:
        """属性値ごとのサマリーを出力します。

        Args:
            summaries: サマリー集計結果。
            group_by: 集計キー。
            output_file: 出力先。
            arg_format: 出力形式。
            attribute_columns: 出力する属性値列。
        """
        remaining_columns = sorted({cast(AttributeValueKey, key) for summary in summaries for key in summary.value_counts} - set(attribute_columns))
        attribute_columns = [*attribute_columns, *remaining_columns]
        if arg_format == OutputFormat.CSV:
            basic_columns = [(value, "", "") for value in [*group_by, "task_count", "input_data_count"]]
            columns = [*basic_columns, *attribute_columns]
            rows: list[dict[tuple[str, str, str], object]] = []
            for summary in summaries:
                row: dict[tuple[str, str, str], object] = {(key, "", ""): value for key, value in summary.group_values.items()}
                row[("task_count", "", "")] = summary.task_count
                row[("input_data_count", "", "")] = summary.input_data_count
                row.update(cast(dict[tuple[str, str, str], object], dict(summary.value_counts)))
                rows.append(row)
            df = pandas.DataFrame(rows, columns=pandas.MultiIndex.from_tuples(columns))
            df = df.fillna(dict.fromkeys(attribute_columns, 0))
            print_csv(df, output=output_file)
            return

        json_rows = [
            {
                **summary.group_values,
                "task_count": summary.task_count,
                "input_data_count": summary.input_data_count,
                "annotation_count_by_attribute_value": encode_annotation_count_by_attribute(Counter(cast(dict[AttributeValueKey, int], summary.value_counts))),
            }
            for summary in summaries
        ]
        print_json(json_rows, is_pretty=arg_format == OutputFormat.PRETTY_JSON, output=output_file)

    def attribute_value_columns(
        self,
        *,
        additional_attribute_names: Collection[AttributeNameKey] | None,
        specified_attribute_names: Collection[AttributeNameKey] | None,
        target_label_names: Collection[str] | None = None,
    ) -> list[tuple[str, str, str]]:
        """CSVの属性値列を、アノテーション仕様の順序に合わせて返します。"""
        if specified_attribute_names is not None:
            attribute_value_keys = self.annotation_specs.get_attribute_value_keys_for_target_attributes(specified_attribute_names)
        elif additional_attribute_names is not None:
            default_selective_attributes = self.annotation_specs.selective_attribute_name_keys()
            combined_attributes = list(set(default_selective_attributes) | set(additional_attribute_names))
            attribute_value_keys = self.annotation_specs.get_attribute_value_keys_for_target_attributes(combined_attributes)
        else:
            attribute_value_keys = self.annotation_specs.selective_attribute_value_keys()

        if target_label_names is not None:
            attribute_value_keys = [e for e in attribute_value_keys if e[0] in target_label_names]
        if self.name_translator is not None:
            attribute_value_keys = [self.name_translator.attribute_value_key(e) for e in attribute_value_keys]
        return attribute_value_keys

    @staticmethod
    def to_label_count_dict(counter: AnnotationCounterByTask | AnnotationCounterByInputData) -> dict[str, Any]:
        """ラベルごとのアノテーション数だけを含むdictに変換します。"""
        result = counter.to_dict(encode_json=True)
        result.pop("annotation_count_by_attribute")
        if not counter.task_metadata:
            result.pop("task_metadata")
        return result

    @staticmethod
    def to_attribute_value_count_dict(counter: AnnotationCounterByTask | AnnotationCounterByInputData) -> dict[str, Any]:
        """属性値ごとのアノテーション数だけを含むdictに変換します。"""
        result = counter.to_dict(encode_json=True)
        result.pop("annotation_count")
        result.pop("annotation_count_by_label")
        result["annotation_count_by_attribute_value"] = result.pop("annotation_count_by_attribute")
        if not counter.task_metadata:
            result.pop("task_metadata")
        return result


class CountAnnotation(CommandLine):
    """
    アノテーション数を出力する。
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace, *, count_target: str) -> None:
        super().__init__(service, facade, args)
        self.count_target = count_target

    def main(self) -> None:
        args = self.args

        project_id: str = args.project_id
        with_task_metadata: bool = args.with_task_metadata
        super().require_project_access(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        annotation_path = args.annotation
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        annotation_specs = AnnotationSpecs(self.service, project_id)
        additional_attribute_names, specified_attribute_names = self.get_target_attribute_names(annotation_specs)
        target_label_names = self.get_target_label_names(annotation_specs)

        group_by: list[str] = args.group_by
        output_file: Path = args.output
        arg_format = OutputFormat(args.format)
        with_per_input_data: bool = args.with_per_input_data
        name_translator = AnnotationNameTranslator.from_project(self.service, project_id) if args.use_japanese_name else None
        main_obj = CountAnnotationMain(annotation_specs, name_translator)

        downloading_obj = DownloadingFile(self.service)

        def download_and_process_annotation(temp_dir: Path, *, is_latest: bool, annotation_path: Path | None) -> None:
            task_json_path: Path | None = None
            if group_by == [INPUT_DATA_ID_GROUP] or with_task_metadata or needs_task_metadata(group_by):
                task_json_path = downloading_obj.download_task_json_to_dir(
                    project_id,
                    temp_dir,
                    is_latest=is_latest,
                )

            if with_task_metadata or needs_task_metadata(group_by):
                assert task_json_path is not None
                task_metadata_by_task_id = get_task_metadata_by_task_id(task_json_path)
                task_metadata_keys = get_task_metadata_keys(task_metadata_by_task_id)
            else:
                task_metadata_by_task_id = None
                task_metadata_keys = []

            if annotation_path is None:
                annotation_path = downloading_obj.download_annotation_zip_to_dir(
                    project_id,
                    temp_dir,
                    is_latest=is_latest,
                )

            if self.count_target == CountTarget.LABEL:
                main_obj.print_label_count(
                    annotation_path=annotation_path,
                    task_json_path=task_json_path,
                    group_by=group_by,
                    arg_format=arg_format,
                    output_file=output_file,
                    target_task_ids=task_id_list,
                    task_query=task_query,
                    target_label_names=target_label_names,
                    with_per_input_data=with_per_input_data,
                    task_metadata_keys=task_metadata_keys,
                    task_metadata_by_task_id=task_metadata_by_task_id,
                )
            else:
                main_obj.print_attribute_value_count(
                    annotation_path=annotation_path,
                    task_json_path=task_json_path,
                    group_by=group_by,
                    arg_format=arg_format,
                    output_file=output_file,
                    target_task_ids=task_id_list,
                    task_query=task_query,
                    additional_attribute_names=additional_attribute_names,
                    specified_attribute_names=specified_attribute_names,
                    target_label_names=target_label_names,
                    with_per_input_data=with_per_input_data,
                    task_metadata_keys=task_metadata_keys,
                    task_metadata_by_task_id=task_metadata_by_task_id,
                )

        if args.temp_dir is not None:
            download_and_process_annotation(temp_dir=args.temp_dir, is_latest=args.latest, annotation_path=annotation_path)
        else:
            with tempfile.TemporaryDirectory() as str_temp_dir:
                download_and_process_annotation(temp_dir=Path(str_temp_dir), is_latest=args.latest, annotation_path=annotation_path)

    def get_target_attribute_names(
        self,
        annotation_specs: AnnotationSpecs,
    ) -> tuple[list[AttributeNameKey] | None, list[AttributeNameKey] | None]:
        """属性値集計で利用する属性名を取得します。"""
        if self.count_target != CountTarget.ATTRIBUTE_VALUE:
            return None, None

        args = self.args
        if args.additional_attribute_name is not None:
            attribute_name_str_list = annofabcli.common.cli.get_list_from_args(args.additional_attribute_name)
            additional_attribute_names, not_found_names = annotation_specs.get_attribute_name_keys_by_attribute_names(attribute_name_str_list)
            if len(not_found_names) > 0:
                logger.warning(f"指定された属性名のうち、アノテーション仕様に見つからなかった属性名があります。 :: {not_found_names}")
            return additional_attribute_names, None

        if args.attribute_name is not None:
            attribute_name_str_list = annofabcli.common.cli.get_list_from_args(args.attribute_name)
            specified_attribute_names, not_found_names = annotation_specs.get_attribute_name_keys_by_attribute_names(attribute_name_str_list)
            if len(not_found_names) > 0:
                logger.warning(f"指定された属性名のうち、アノテーション仕様に見つからなかった属性名があります。 :: {not_found_names}")
            return None, specified_attribute_names

        return None, None

    def get_target_label_names(self, annotation_specs: AnnotationSpecs) -> list[str] | None:
        """集計で利用するラベル名を取得します。"""
        if self.args.label_name is None:
            return None

        label_name_list = annofabcli.common.cli.get_list_from_args(self.args.label_name)
        target_label_names, not_found_names = annotation_specs.get_label_keys_by_label_names(label_name_list)
        if len(not_found_names) > 0:
            logger.warning(f"指定されたラベル名のうち、アノテーション仕様に見つからなかったラベル名があります。 :: {not_found_names}")
        return target_label_names


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """
    count_annotation_by_* コマンド共通の引数を追加します。
    """
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "--annotation",
        type=Path,
        help="アノテーションzip、またはzipを展開したディレクトリを指定します。指定しない場合はAnnofabからダウンロードします。",
    )
    argument_parser.add_project_id()
    parser.add_argument(
        "--group_by",
        type=str,
        nargs="+",
        default=[TASK_ID_GROUP],
        help="アノテーションの個数を集約する項目を指定します。指定できる値は task_id, input_data_id, project_id, task_phase, task_phase_stage, task_status, task_metadata.<key> です。"
        "サマリー項目は複数指定できます。",
    )
    argument_parser.add_format(
        choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON],
        default=OutputFormat.CSV,
    )
    argument_parser.add_output()
    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="集計対象タスクを絞り込むためのクエリ条件をJSON形式で指定します。使用できるキーは task_id, status, phase, phase_stage です。"
        " ``file://`` を先頭に付けると、JSON形式のファイルを指定できます。",
    )
    argument_parser.add_task_id(required=False)
    parser.add_argument(
        "--latest",
        action="store_true",
        help="``--annotation`` を指定しないとき、最新のアノテーションzipを参照します。このオプションを指定すると、アノテーションzipを更新するのに数分待ちます。",
    )
    parser.add_argument(
        "--temp_dir",
        type=Path,
        help="指定したディレクトリに、アノテーションZIPなどの一時ファイルをダウンロードします。",
    )
    parser.add_argument("--with_task_metadata", action="store_true", help="タスクメタデータを出力します。CSVでは ``task_metadata.<key>`` 列、JSONでは ``task_metadata`` キーに出力します。")

    parser.add_argument(
        "--with_per_input_data",
        action="store_true",
        help="タスク単位CSVに入力データあたりのアノテーション数を追加で出力します。動画プロジェクトではフレームあたりの平均として利用できます。",
    )
    add_use_japanese_name_argument(parser)


def add_label_name_argument(parser: argparse.ArgumentParser, *, target_description: str) -> None:
    """集計対象ラベル名を指定する引数を追加します。"""
    parser.add_argument(
        "--label_name",
        type=str,
        nargs="+",
        help=f"集計対象とするラベルの英語名を指定します。指定したラベルに属する{target_description}のみが集計対象になります。"
        " ``file://`` を先頭に付けると、ラベル名が記載されたファイルを指定できます。",
    )


def add_attribute_value_arguments(parser: argparse.ArgumentParser) -> None:
    """
    count_annotation_by_attribute_value コマンドの引数を追加します。
    """
    attribute_group = parser.add_mutually_exclusive_group()
    attribute_group.add_argument(
        "--additional_attribute_name",
        type=str,
        nargs="+",
        help="デフォルトで集計される選択肢系の属性（ドロップダウン、ラジオボタン、チェックボックス）に加えて、集計したい属性の英語名を指定します。"
        "ラベル名に関係なく、デフォルト属性と指定した属性名を持つ属性が集計対象になります。"
        " ``file://`` を先頭に付けると、属性名が記載されたファイルを指定できます。",
    )
    add_label_name_argument(parser, target_description="属性値")
    attribute_group.add_argument(
        "--attribute_name",
        type=str,
        nargs="+",
        help="集計対象とする属性の英語名を指定します。指定した属性名のみが集計対象になります（デフォルトの選択肢系属性は含まれません）。"
        "ラベル名に関係なく、指定した属性名を持つ属性のみが集計対象になります。"
        " ``file://`` を先頭に付けると、属性名が記載されたファイルを指定できます。",
    )


def validate_with_per_input_data(args: argparse.Namespace, subcommand_name: str) -> bool:
    """``--with_per_input_data`` と他オプションの組み合わせを検証します。"""
    if not args.with_per_input_data:
        return True

    common_message = f"annofabcli annotation_zip {subcommand_name}: error:"
    if args.group_by != [TASK_ID_GROUP]:
        print(f"{common_message} `--with_per_input_data`は`--group_by task_id`を指定したときだけ使用できます。", file=sys.stderr)  # noqa: T201
        return False

    if args.format != OutputFormat.CSV.value:
        print(f"{common_message} `--with_per_input_data`は`--format csv`を指定したときだけ使用できます。", file=sys.stderr)  # noqa: T201
        return False

    return True


def validate_count_options(args: argparse.Namespace, subcommand_name: str) -> bool:
    """集計オプションの組み合わせを検証します。

    Args:
        args: コマンドライン引数。
        subcommand_name: サブコマンド名。

    Returns:
        正しい組み合わせの場合はTrue。
    """
    common_message = f"annofabcli annotation_zip {subcommand_name}: error:"
    error_message = validate_group_by(args.group_by)
    if error_message is not None:
        print(f"{common_message} {error_message}", file=sys.stderr)  # noqa: T201
        return False
    if args.with_task_metadata and is_summary_group(args.group_by):
        print(f"{common_message} `--with_task_metadata`は`--group_by task_id`または`--group_by input_data_id`を指定したときだけ使用できます。", file=sys.stderr)  # noqa: T201
        return False
    return validate_with_per_input_data(args, subcommand_name)


def main_label(args: argparse.Namespace) -> None:
    if not validate_count_options(args, "count_annotation_by_label"):
        sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
    service = annofabcli.common.cli.build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CountAnnotation(service, facade, args, count_target=CountTarget.LABEL).main()


def main_attribute_value(args: argparse.Namespace) -> None:
    if not validate_count_options(args, "count_annotation_by_attribute_value"):
        sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
    service = annofabcli.common.cli.build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CountAnnotation(service, facade, args, count_target=CountTarget.ATTRIBUTE_VALUE).main()
