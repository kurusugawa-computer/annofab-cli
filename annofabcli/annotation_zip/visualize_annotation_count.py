from __future__ import annotations

import argparse
import collections
import logging
import math
import tempfile
from collections import defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi
import bokeh
import numpy
import pandas
from annofabapi.models import ProjectMemberRole
from bokeh.models import LayoutDOM
from bokeh.models.widgets.markups import Div
from bokeh.plotting import figure

import annofabcli.common.cli
from annofabcli.annotation_zip.annotation_count import AnnotationCounter, AnnotationSpecs, AttributeNameKey, AttributeValueKey, GroupBy
from annofabcli.annotation_zip.annotation_name import AnnotationNameTranslator, add_use_japanese_name_argument
from annofabcli.annotation_zip.count_annotation import CountAnnotationMain, CountTarget
from annofabcli.common.bokeh import convert_1d_figure_list_to_2d, create_pretext_from_metadata
from annofabcli.common.cli import ArgumentParser, CommandLine, positive_int
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.statistics.histogram import create_histogram_figure, get_bin_edges, get_sub_title_from_series

logger = logging.getLogger(__name__)

BIN_COUNT = 20


def _get_y_axis_label(group_by: GroupBy) -> str:
    if group_by == GroupBy.TASK_ID:
        return "タスク数"
    elif group_by == GroupBy.INPUT_DATA_ID:
        return "入力データ数"
    else:
        raise RuntimeError(f"group_by='{group_by}'が対象外です。")


def convert_to_2d_figure_list(figures_dict: dict[tuple[str, str], list[figure]], *, ncols: int = 4) -> list[list[LayoutDOM | None]]:
    """
    grid layout用に2次元のfigureリストに変換する。
    """
    row_list: list[list[LayoutDOM | None]] = []

    for (label_name, attribute_name), figure_list in figures_dict.items():
        row_list.append([Div(text=f"<h3>ラベル名='{label_name}', 属性名='{attribute_name}'</h3>")])

        for i in range(math.ceil(len(figure_list) / ncols)):
            start = i * ncols
            end = (i + 1) * ncols
            row: list[LayoutDOM | None] = []
            row.extend(figure_list[start:end])
            if len(row) < ncols:
                row.extend([None] * (ncols - len(row)))
            row_list.append(row)

    return row_list


def get_only_selective_attribute(columns: list[AttributeValueKey]) -> list[AttributeValueKey]:
    """
    選択肢系の属性に対応する列のみ抽出する。
    属性値の個数が多い場合、非選択肢系の属性（トラッキングIDやアノテーションリンクなど）の可能性があるため、それらを除外する。
    CSVの列数を増やしすぎないための対策。
    """
    SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT = 20  # noqa: N806
    attribute_name_list: list[AttributeNameKey] = []
    for label, attribute_name, _ in columns:
        attribute_name_list.append((label, attribute_name))

    non_selective_attribute_names = {key for key, value in collections.Counter(attribute_name_list).items() if value > SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT}

    if len(non_selective_attribute_names) > 0:
        logger.debug(f"以下の属性は値の個数が{SELECTIVE_ATTRIBUTE_VALUE_MAX_COUNT}を超えていたため、集計しません。 :: {non_selective_attribute_names}")

    return [(label, attribute_name, attribute_value) for (label, attribute_name, attribute_value) in columns if (label, attribute_name) not in non_selective_attribute_names]


def plot_label_histogram(
    counter_list: Sequence[AnnotationCounter],
    group_by: GroupBy,
    output_file: Path,
    *,
    prior_keys: list[str] | None = None,
    bin_width: int | None = None,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    ラベルごとのアノテーション数のヒストグラムを出力する。

    Args:
        prior_keys: 優先して表示するcounter_listのキーlist
        bin_width: ビンの幅
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムを描画しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
        metadata: HTMLファイルの上部に表示するメタデータです。
    """

    def create_df() -> pandas.DataFrame:
        all_label_key_set = {key for c in counter_list for key in c.annotation_count_by_label}
        if prior_keys is not None:
            remaining_columns = sorted(all_label_key_set - set(prior_keys))
            columns = prior_keys + remaining_columns
        else:
            columns = sorted(all_label_key_set)

        df = pandas.DataFrame([e.annotation_count_by_label for e in counter_list], columns=columns)
        df.fillna(0, inplace=True)
        return df

    df = create_df()

    if arrange_bin_edge:
        histogram_range = (
            df.min(numeric_only=True).min(),
            df.max(numeric_only=True).max(),
        )
    else:
        histogram_range = None

    y_axis_label = _get_y_axis_label(group_by)

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(f"以下のラベルは、すべてのタスクでアノテーション数が0であるためヒストグラムを描画しません。 :: {set(df.columns) - set(columns)}")
    else:
        columns = df.columns

    max_annotation_count = df.max(numeric_only=True).max()

    figure_list_2d: list[list[LayoutDOM | None]] = [
        [
            Div(text="<h3>アノテーション数の分布（ラベル名ごと）</h3>"),
        ]
    ]

    if metadata is not None:
        figure_list_2d.append([create_pretext_from_metadata(metadata)])

    logger.debug(f"{len(columns)}個のラベルごとのヒストグラムが描画されたhtmlファイルを出力します。")
    histogram_list: list[figure] = []
    for col in columns:
        if bin_width is not None:
            if arrange_bin_edge:
                bin_edges = get_bin_edges(min_value=0, max_value=max_annotation_count, bin_width=bin_width)
            else:
                bin_edges = get_bin_edges(min_value=0, max_value=df[col].max(), bin_width=bin_width)

            hist, bin_edges = numpy.histogram(df[col], bins=bin_edges, range=histogram_range)
        else:
            hist, bin_edges = numpy.histogram(df[col], bins=BIN_COUNT, range=histogram_range)

        fig = create_histogram_figure(
            hist,
            bin_edges,
            x_axis_label="アノテーション数",
            y_axis_label=y_axis_label,
            title=str(col),
            sub_title=get_sub_title_from_series(df[col], decimals=2),
        )
        histogram_list.append(fig)

    figure_list_2d.extend(convert_1d_figure_list_to_2d(histogram_list))
    bokeh_obj = bokeh.layouts.gridplot(figure_list_2d)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()

    html_title = "アノテーション数の分布（ラベル名ごと）"
    if metadata is not None and "project_title" in metadata:
        html_title = f"{html_title}({metadata['project_title']})"

    bokeh.plotting.output_file(output_file, title=html_title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


def plot_attribute_histogram(  # noqa: PLR0915
    counter_list: Sequence[AnnotationCounter],
    group_by: GroupBy,
    output_file: Path,
    *,
    prior_keys: list[AttributeValueKey] | None = None,
    bin_width: int | None = None,
    exclude_empty_value: bool = False,
    arrange_bin_edge: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    属性値ごとのアノテーション数のヒストグラムを出力する。

    Args:
        prior_keys: 優先して表示するcounter_listのキーlist
        exclude_empty_value: Trueならば、すべての値が0である列のヒストグラムを描画しません。
        arrange_bin_edge: Trueならば、ヒストグラムの範囲をすべてのヒストグラムで一致させます。
        metadata: HTMLファイルの上部に表示するメタデータです。

    """

    def create_df() -> pandas.DataFrame:
        all_key_set = {key for c in counter_list for key in c.annotation_count_by_attribute}
        if prior_keys is not None:
            remaining_columns = list(all_key_set - set(prior_keys))
            remaining_columns_selective_attribute = sorted(get_only_selective_attribute(remaining_columns))
            columns = prior_keys + remaining_columns_selective_attribute
        else:
            remaining_columns_selective_attribute = sorted(get_only_selective_attribute(list(all_key_set)))
            columns = remaining_columns_selective_attribute

        df = pandas.DataFrame([e.annotation_count_by_attribute for e in counter_list], columns=columns)
        df.fillna(0, inplace=True)

        return df

    df = create_df()
    y_axis_label = _get_y_axis_label(group_by)

    if arrange_bin_edge:
        histogram_range = (
            df.min(numeric_only=True).min(),
            df.max(numeric_only=True).max(),
        )
    else:
        histogram_range = None

    if exclude_empty_value:
        # すべての値が0である列を除外する
        columns = [col for col in df.columns if df[col].sum() > 0]
        if len(columns) < len(df.columns):
            logger.debug(f"以下の属性値は、すべてのタスクでアノテーション数が0であるためヒストグラムを描画しません。 :: {set(df.columns) - set(columns)}")
    else:
        columns = df.columns

    max_annotation_count = df.max(numeric_only=True).max()

    figure_list_2d: list[list[LayoutDOM | None]] = [
        [
            Div(text="<h3>アノテーション数の分布（属性値ごと）</h3>"),
        ]
    ]

    if metadata is not None:
        figure_list_2d.append([create_pretext_from_metadata(metadata)])

    figures_dict = defaultdict(list)
    logger.debug(f"{len(columns)}個の属性値ごとのヒストグラムが描画されたhtmlファイルを出力します。")
    for col in columns:
        header = (str(col[0]), str(col[1]))  # ラベル名, 属性名

        if bin_width is not None:
            if arrange_bin_edge:
                bin_edges = get_bin_edges(min_value=0, max_value=max_annotation_count, bin_width=bin_width)
            else:
                bin_edges = get_bin_edges(min_value=0, max_value=df[col].max(), bin_width=bin_width)

            hist, bin_edges = numpy.histogram(df[col], bins=bin_edges, range=histogram_range)
        else:
            hist, bin_edges = numpy.histogram(df[col], bins=BIN_COUNT, range=histogram_range)

        fig = create_histogram_figure(
            hist,
            bin_edges,
            x_axis_label="アノテーション数",
            y_axis_label=y_axis_label,
            title=f"{col[0]},{col[1]},{col[2]}",
            sub_title=get_sub_title_from_series(df[col], decimals=2),
        )
        figures_dict[header].append(fig)

    figure_list_2d.extend(convert_to_2d_figure_list(figures_dict))
    bokeh_obj = bokeh.layouts.gridplot(figure_list_2d)
    output_file.parent.mkdir(exist_ok=True, parents=True)
    bokeh.plotting.reset_output()
    html_title = "アノテーション数の分布（属性値ごと）"
    if metadata is not None and "project_title" in metadata:
        html_title = f"{html_title}({metadata['project_title']})"

    bokeh.plotting.output_file(output_file, title=html_title)
    bokeh.plotting.save(bokeh_obj)
    logger.info(f"'{output_file}'を出力しました。")


@dataclass(frozen=True)
class AttributeNameOptions:
    """属性値ごとの可視化対象を絞り込むラベル名と属性名。"""

    target_label_names: Collection[str] | None = None
    """集計対象とするラベルの英語名。"""

    additional_attribute_names: Collection[AttributeNameKey] | None = None
    """デフォルトの選択系属性に加えて集計対象とする属性名。"""

    specified_attribute_names: Collection[AttributeNameKey] | None = None
    """集計対象とする属性名。"""


class VisualizeAnnotationCountMain:
    def __init__(
        self,
        service: annofabapi.Resource,
        annotation_specs: AnnotationSpecs,
        name_translator: AnnotationNameTranslator | None = None,
    ) -> None:
        """
        Args:
            service: Annofab Web APIのリソース
            annotation_specs: アノテーション仕様
            name_translator: 出力する名称の変換オブジェクト。
        """
        self.service = service
        self.annotation_specs = annotation_specs
        self.name_translator = name_translator
        self.count_annotation = CountAnnotationMain(annotation_specs, name_translator)

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
        prior_keys = self.annotation_specs.label_keys()
        if self.name_translator is not None:
            prior_keys = [self.name_translator.label_name(e) for e in prior_keys]
        plot_label_histogram(
            counter_list,
            group_by=group_by,
            output_file=output_file,
            bin_width=bin_width,
            prior_keys=prior_keys,
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
            target_label_names=attribute_name_options.target_label_names,
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
                target_label_names=attribute_name_options.target_label_names,
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
        super().require_project_access(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        annotation_specs = AnnotationSpecs(self.service, project_id)
        group_by = GroupBy(args.group_by)
        output_file = Path(args.output)
        name_translator = AnnotationNameTranslator.from_project(self.service, project_id) if args.use_japanese_name else None
        main_obj = VisualizeAnnotationCountMain(self.service, annotation_specs, name_translator)

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
        """属性値の可視化で利用するラベル名と属性名を取得します。

        Args:
            annotation_specs: 対象プロジェクトのアノテーション仕様。

        Returns:
            指定されたラベル名と属性名による絞り込み条件。
        """
        if self.count_target != CountTarget.ATTRIBUTE_VALUE:
            return AttributeNameOptions()

        args = self.args
        target_label_names = None
        if args.label_name is not None:
            label_name_list = annofabcli.common.cli.get_list_from_args(args.label_name)
            target_label_names, not_found_names = annotation_specs.get_label_keys_by_label_names(label_name_list)
            if len(not_found_names) > 0:
                logger.warning(f"指定されたラベル名のうち、アノテーション仕様に見つからなかったラベル名があります。 :: {not_found_names}")

        if args.additional_attribute_name is not None:
            attribute_name_str_list = annofabcli.common.cli.get_list_from_args(args.additional_attribute_name)
            additional_attribute_names, not_found_names = annotation_specs.get_attribute_name_keys_by_attribute_names(attribute_name_str_list)
            if len(not_found_names) > 0:
                logger.warning(f"指定された属性名のうち、アノテーション仕様に見つからなかった属性名があります。 :: {not_found_names}")
            return AttributeNameOptions(target_label_names=target_label_names, additional_attribute_names=additional_attribute_names)

        if args.attribute_name is not None:
            attribute_name_str_list = annofabcli.common.cli.get_list_from_args(args.attribute_name)
            specified_attribute_names, not_found_names = annotation_specs.get_attribute_name_keys_by_attribute_names(attribute_name_str_list)
            if len(not_found_names) > 0:
                logger.warning(f"指定された属性名のうち、アノテーション仕様に見つからなかった属性名があります。 :: {not_found_names}")
            return AttributeNameOptions(target_label_names=target_label_names, specified_attribute_names=specified_attribute_names)

        return AttributeNameOptions(target_label_names=target_label_names)


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
        type=positive_int,
        help=f"ヒストグラムのビンの幅を1以上の整数で指定します。指定しない場合は、ビンの個数が{BIN_COUNT}になるようにビンの幅が調整されます。",
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
    add_use_japanese_name_argument(parser)


def main_label(args: argparse.Namespace) -> None:
    service = annofabcli.common.cli.build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeAnnotationCount(service, facade, args, count_target=CountTarget.LABEL).main()


def main_attribute_value(args: argparse.Namespace) -> None:
    service = annofabcli.common.cli.build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeAnnotationCount(service, facade, args, count_target=CountTarget.ATTRIBUTE_VALUE).main()
