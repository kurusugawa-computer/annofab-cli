from __future__ import annotations

import argparse
import logging
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Any, cast

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.cli import ArgumentParser, CommandLine
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.common.utils import print_json
from annofabcli.statistics.list_annotation_count import (
    AnnotationCounterByInputData,
    AnnotationCounterByTask,
    AnnotationSpecs,
    AttributeCountCsv,
    AttributeNameKey,
    GroupBy,
    LabelCountCsv,
    ListAnnotationCounterByInputData,
    ListAnnotationCounterByTask,
    ListAnnotationCountMain,
)

logger = logging.getLogger(__name__)


class CountTarget:
    """集計対象を表す定数。"""

    LABEL = "label"
    """ラベルごとのアノテーション数"""

    ATTRIBUTE_VALUE = "attribute_value"
    """属性値ごとのアノテーション数"""


class CountAnnotationMain:
    def __init__(self, annotation_specs: AnnotationSpecs) -> None:
        """
        Args:
            annotation_specs: アノテーション仕様
        """
        self.annotation_specs = annotation_specs

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
            return ListAnnotationCounterByInputData(
                target_attribute_names_only=target_attribute_names_only,
                frame_no_map=frame_no_map,
            ).get_annotation_counter_list(
                annotation_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
            )

        return ListAnnotationCounterByTask(
            target_attribute_names_only=target_attribute_names_only,
        ).get_annotation_counter_list(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )

    def print_label_count(
        self,
        annotation_path: Path,
        group_by: GroupBy,
        output_file: Path,
        arg_format: OutputFormat,
        *,
        task_json_path: Path | None = None,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
    ) -> None:
        """
        ラベルごとのアノテーション数を出力します。
        """
        counter_list = self.get_counter_list(
            annotation_path,
            group_by,
            task_json_path=task_json_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )
        if arg_format == OutputFormat.CSV:
            label_columns = self.annotation_specs.label_keys()
            if group_by == GroupBy.INPUT_DATA_ID:
                LabelCountCsv().print_csv_by_input_data(cast(list[AnnotationCounterByInputData], counter_list), output_file, prior_label_columns=label_columns)
            else:
                LabelCountCsv().print_csv_by_task(cast(list[AnnotationCounterByTask], counter_list), output_file, prior_label_columns=label_columns)
            return

        print_json(
            [self.to_label_count_dict(e) for e in counter_list],
            is_pretty=arg_format == OutputFormat.PRETTY_JSON,
            output=output_file,
        )

    def print_attribute_value_count(
        self,
        annotation_path: Path,
        group_by: GroupBy,
        output_file: Path,
        arg_format: OutputFormat,
        *,
        task_json_path: Path | None = None,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
        additional_attribute_names: Collection[AttributeNameKey] | None = None,
        specified_attribute_names: Collection[AttributeNameKey] | None = None,
    ) -> None:
        """
        属性値ごとのアノテーション数を出力します。
        """
        counter_list = self.get_counter_list(
            annotation_path,
            group_by,
            task_json_path=task_json_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
            additional_attribute_names=additional_attribute_names,
            specified_attribute_names=specified_attribute_names,
        )
        if arg_format == OutputFormat.CSV:
            attribute_columns = self.attribute_value_columns(
                additional_attribute_names=additional_attribute_names,
                specified_attribute_names=specified_attribute_names,
            )
            if group_by == GroupBy.INPUT_DATA_ID:
                AttributeCountCsv().print_csv_by_input_data(cast(list[AnnotationCounterByInputData], counter_list), output_file, prior_attribute_columns=attribute_columns)
            else:
                AttributeCountCsv().print_csv_by_task(cast(list[AnnotationCounterByTask], counter_list), output_file, prior_attribute_columns=attribute_columns)
            return

        print_json(
            [self.to_attribute_value_count_dict(e) for e in counter_list],
            is_pretty=arg_format == OutputFormat.PRETTY_JSON,
            output=output_file,
        )

    def attribute_value_columns(
        self,
        *,
        additional_attribute_names: Collection[AttributeNameKey] | None,
        specified_attribute_names: Collection[AttributeNameKey] | None,
    ) -> list[tuple[str, str, str]]:
        """CSVの属性値列を、アノテーション仕様の順序に合わせて返します。"""
        if specified_attribute_names is not None:
            return self.annotation_specs.get_attribute_value_keys_for_target_attributes(specified_attribute_names)

        if additional_attribute_names is not None:
            default_selective_attributes = self.annotation_specs.selective_attribute_name_keys()
            combined_attributes = list(set(default_selective_attributes) | set(additional_attribute_names))
            return self.annotation_specs.get_attribute_value_keys_for_target_attributes(combined_attributes)

        return self.annotation_specs.selective_attribute_value_keys()

    @staticmethod
    def to_label_count_dict(counter: AnnotationCounterByTask | AnnotationCounterByInputData) -> dict[str, Any]:
        """ラベルごとのアノテーション数だけを含むdictに変換します。"""
        result = counter.to_dict(encode_json=True)
        result.pop("annotation_count_by_attribute")
        return result

    @staticmethod
    def to_attribute_value_count_dict(counter: AnnotationCounterByTask | AnnotationCounterByInputData) -> dict[str, Any]:
        """属性値ごとのアノテーション数だけを含むdictに変換します。"""
        result = counter.to_dict(encode_json=True)
        result.pop("annotation_count_by_label")
        result["annotation_count_by_attribute_value"] = result.pop("annotation_count_by_attribute")
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
        super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        annotation_path = args.annotation
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        annotation_specs = AnnotationSpecs(self.service, project_id)
        additional_attribute_names, specified_attribute_names = self.get_target_attribute_names(annotation_specs)

        group_by = GroupBy(args.group_by)
        output_file: Path = args.output
        arg_format = OutputFormat(args.format)
        main_obj = CountAnnotationMain(annotation_specs)

        downloading_obj = DownloadingFile(self.service)

        def download_and_process_annotation(temp_dir: Path, *, is_latest: bool, annotation_path: Path | None) -> None:
            task_json_path: Path | None = None
            if group_by == GroupBy.INPUT_DATA_ID:
                task_json_path = downloading_obj.download_task_json_to_dir(
                    project_id,
                    temp_dir,
                    is_latest=is_latest,
                )

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
        choices=[GroupBy.TASK_ID.value, GroupBy.INPUT_DATA_ID.value],
        default=GroupBy.TASK_ID.value,
        help="アノテーションの個数をどの単位で集約するかを指定してます。",
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
    attribute_group.add_argument(
        "--attribute_name",
        type=str,
        nargs="+",
        help="集計対象とする属性の英語名を指定します。指定した属性名のみが集計対象になります（デフォルトの選択肢系属性は含まれません）。"
        "ラベル名に関係なく、指定した属性名を持つ属性のみが集計対象になります。"
        " ``file://`` を先頭に付けると、属性名が記載されたファイルを指定できます。",
    )


def main_label(args: argparse.Namespace) -> None:
    service = annofabcli.common.cli.build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CountAnnotation(service, facade, args, count_target=CountTarget.LABEL).main()


def main_attribute_value(args: argparse.Namespace) -> None:
    service = annofabcli.common.cli.build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CountAnnotation(service, facade, args, count_target=CountTarget.ATTRIBUTE_VALUE).main()
