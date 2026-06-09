from __future__ import annotations

import argparse
import logging
import tempfile
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

import annofabapi
from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.annotation_zip.count_annotation import CountAnnotationMain, CountTarget
from annofabcli.common.cli import ArgumentParser, CommandLine
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.statistics.list_annotation_count import AnnotationSpecs, AttributeNameKey, GroupBy
from annofabcli.statistics.visualize_annotation_count import BIN_COUNT, plot_attribute_histogram, plot_label_histogram

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AttributeNameOptions:
    """属性値ごとの可視化対象とする属性名。"""

    additional_attribute_names: Collection[AttributeNameKey] | None = None
    """デフォルトの選択系属性に加えて集計対象とする属性名。"""

    specified_attribute_names: Collection[AttributeNameKey] | None = None
    """集計対象とする属性名。"""


class VisualizeAnnotationCountMain:
    def __init__(self, service: annofabapi.Resource, annotation_specs: AnnotationSpecs) -> None:
        """
        Args:
            service: Annofab Web APIのリソース
            annotation_specs: アノテーション仕様
        """
        self.service = service
        self.annotation_specs = annotation_specs
        self.count_annotation = CountAnnotationMain(annotation_specs)

    def visualize_label_count(
        self,
        annotation_path: Path,
        group_by: GroupBy,
        output_file: Path,
        *,
        project_id: str,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
        bin_width: int | None = None,
        exclude_empty_value: bool = False,
        arrange_bin_edge: bool = False,
    ) -> None:
        """
        ラベルごとのアノテーション数をヒストグラムで可視化します。
        """
        counter_list = self.count_annotation.get_counter_list(
            annotation_path,
            group_by,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )
        metadata = self.create_metadata(project_id=project_id, target_task_ids=target_task_ids, task_query=task_query)
        plot_label_histogram(
            counter_list,
            group_by=group_by,
            output_file=output_file,
            bin_width=bin_width,
            prior_keys=self.annotation_specs.label_keys(),
            exclude_empty_value=exclude_empty_value,
            arrange_bin_edge=arrange_bin_edge,
            metadata=metadata,
        )

    def visualize_attribute_value_count(
        self,
        annotation_path: Path,
        group_by: GroupBy,
        output_file: Path,
        *,
        project_id: str,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
        bin_width: int | None = None,
        exclude_empty_value: bool = False,
        arrange_bin_edge: bool = False,
        attribute_name_options: AttributeNameOptions | None = None,
    ) -> None:
        """
        属性値ごとのアノテーション数をヒストグラムで可視化します。
        """
        attribute_name_options = attribute_name_options if attribute_name_options is not None else AttributeNameOptions()
        counter_list = self.count_annotation.get_counter_list(
            annotation_path,
            group_by,
            target_task_ids=target_task_ids,
            task_query=task_query,
            additional_attribute_names=attribute_name_options.additional_attribute_names,
            specified_attribute_names=attribute_name_options.specified_attribute_names,
        )
        metadata = self.create_metadata(project_id=project_id, target_task_ids=target_task_ids, task_query=task_query)
        plot_attribute_histogram(
            counter_list,
            group_by=group_by,
            output_file=output_file,
            bin_width=bin_width,
            prior_keys=self.count_annotation.attribute_value_columns(
                additional_attribute_names=attribute_name_options.additional_attribute_names,
                specified_attribute_names=attribute_name_options.specified_attribute_names,
            ),
            exclude_empty_value=exclude_empty_value,
            arrange_bin_edge=arrange_bin_edge,
            metadata=metadata,
        )

    def create_metadata(
        self,
        *,
        project_id: str,
        target_task_ids: Collection[str] | None,
        task_query: TaskQuery | None,
    ) -> dict[str, object]:
        """HTMLの上部に表示するメタデータを作成します。"""
        project, _ = self.service.api.get_project(project_id)
        return {
            "project_id": project_id,
            "project_title": project["title"],
            "task_query": {k: v for k, v in task_query.to_dict(encode_json=True).items() if v is not None and v is not False} if task_query is not None else None,
            "target_task_ids": target_task_ids,
        }


class VisualizeAnnotationCount(CommandLine):
    """
    アノテーション数をヒストグラムで可視化する。
    """

    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace, *, count_target: str) -> None:
        super().__init__(service, facade, args)
        self.count_target = count_target

    def main(self) -> None:
        args = self.args

        project_id: str = args.project_id
        super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        annotation_specs = AnnotationSpecs(self.service, project_id)
        group_by = GroupBy(args.group_by)
        output_file = Path(args.output)
        main_obj = VisualizeAnnotationCountMain(self.service, annotation_specs)

        def process_annotation(annotation_path: Path) -> None:
            if self.count_target == CountTarget.LABEL:
                main_obj.visualize_label_count(
                    annotation_path=annotation_path,
                    group_by=group_by,
                    output_file=output_file,
                    project_id=project_id,
                    target_task_ids=task_id_list,
                    task_query=task_query,
                    bin_width=args.bin_width,
                    exclude_empty_value=args.exclude_empty_value,
                    arrange_bin_edge=args.arrange_bin_edge,
                )
                return

            attribute_name_options = self.get_attribute_name_options(annotation_specs)
            main_obj.visualize_attribute_value_count(
                annotation_path=annotation_path,
                group_by=group_by,
                output_file=output_file,
                project_id=project_id,
                target_task_ids=task_id_list,
                task_query=task_query,
                bin_width=args.bin_width,
                exclude_empty_value=args.exclude_empty_value,
                arrange_bin_edge=args.arrange_bin_edge,
                attribute_name_options=attribute_name_options,
            )

        if args.annotation is not None:
            process_annotation(args.annotation)
            return

        downloading_obj = DownloadingFile(self.service)
        if args.temp_dir is not None:
            annotation_path = downloading_obj.download_annotation_zip_to_dir(project_id, args.temp_dir, is_latest=args.latest)
            process_annotation(annotation_path)
            return

        with tempfile.TemporaryDirectory() as str_temp_dir:
            annotation_path = downloading_obj.download_annotation_zip_to_dir(project_id, Path(str_temp_dir), is_latest=args.latest)
            process_annotation(annotation_path)

    def get_attribute_name_options(
        self,
        annotation_specs: AnnotationSpecs,
    ) -> AttributeNameOptions:
        """属性値の可視化で利用する属性名を取得します。"""
        if self.count_target != CountTarget.ATTRIBUTE_VALUE:
            return AttributeNameOptions()

        args = self.args
        if args.additional_attribute_name is not None:
            attribute_name_str_list = annofabcli.common.cli.get_list_from_args(args.additional_attribute_name)
            additional_attribute_names, not_found_names = annotation_specs.get_attribute_name_keys_by_attribute_names(attribute_name_str_list)
            if len(not_found_names) > 0:
                logger.warning(f"指定された属性名のうち、アノテーション仕様に見つからなかった属性名があります。 :: {not_found_names}")
            return AttributeNameOptions(additional_attribute_names=additional_attribute_names)

        if args.attribute_name is not None:
            attribute_name_str_list = annofabcli.common.cli.get_list_from_args(args.attribute_name)
            specified_attribute_names, not_found_names = annotation_specs.get_attribute_name_keys_by_attribute_names(attribute_name_str_list)
            if len(not_found_names) > 0:
                logger.warning(f"指定された属性名のうち、アノテーション仕様に見つからなかった属性名があります。 :: {not_found_names}")
            return AttributeNameOptions(specified_attribute_names=specified_attribute_names)

        return AttributeNameOptions()


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """
    visualize_annotation_count_by_* コマンド共通の引数を追加します。
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
        help="アノテーションの個数をどの単位で集約するかを指定します。",
    )
    argument_parser.add_output(required=True, help_message="出力先HTMLファイルのパスを指定します。")
    parser.add_argument(
        "--bin_width",
        type=int,
        help=f"ヒストグラムのビンの幅を指定します。指定しない場合は、ビンの個数が{BIN_COUNT}になるようにビンの幅が調整されます。",
    )
    parser.add_argument(
        "--exclude_empty_value",
        action="store_true",
        help="指定すると、すべてのタスクでアノテーション数が0であるヒストグラムを描画しません。",
    )
    parser.add_argument(
        "--arrange_bin_edge",
        action="store_true",
        help="指定すると、ヒストグラムのデータの範囲とビンの幅がすべてのヒストグラムで一致します。",
    )
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


def main_label(args: argparse.Namespace) -> None:
    service = annofabcli.common.cli.build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeAnnotationCount(service, facade, args, count_target=CountTarget.LABEL).main()


def main_attribute_value(args: argparse.Namespace) -> None:
    service = annofabcli.common.cli.build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeAnnotationCount(service, facade, args, count_target=CountTarget.ATTRIBUTE_VALUE).main()
