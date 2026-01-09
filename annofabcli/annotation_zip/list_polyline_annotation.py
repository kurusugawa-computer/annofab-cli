import argparse
import logging
import math
import sys
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import InputDataType, ProjectMemberRole
from pydantic import BaseModel, ConfigDict

import annofabcli.common.cli
from annofabcli.common.annofab.annotation_zip import lazy_parse_simple_annotation_by_input_data
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import FormatArgument
from annofabcli.common.facade import (
    AnnofabApiFacade,
    TaskQuery,
    match_annotation_with_task_query,
)
from annofabcli.common.utils import print_csv, print_json

logger = logging.getLogger(__name__)


class AnnotationPolylineInfo(BaseModel):
    """
    ポリラインアノテーションの情報
    """

    model_config = ConfigDict(frozen=True)

    project_id: str
    task_id: str
    task_status: str
    task_phase: str
    task_phase_stage: int

    input_data_id: str
    input_data_name: str

    updated_datetime: str | None
    """アノテーションJSONに格納されているアノテーションの更新日時"""

    label: str
    annotation_id: str
    point_count: int
    length: float
    """ポリラインの総長（各線分の長さの合計）"""
    start_point: dict[str, float]
    """始点の座標"""
    end_point: dict[str, float]
    """終点の座標"""
    midpoint: dict[str, float]
    """中点（全頂点の座標平均）"""
    bounding_box_width: float
    """外接矩形の幅"""
    bounding_box_height: float
    """外接矩形の高さ"""
    attributes: dict[str, Any]
    points: list[dict[str, int]]
    """ポリラインの頂点リスト。各頂点は整数座標 {"x": int, "y": int} の形式。
    """


def calculate_polyline_properties(points: list[dict[str, int]]) -> tuple[float, dict[str, float], dict[str, float], dict[str, float], float, float]:
    """
    ポリラインの長さ、始点、終点、中点、外接矩形のサイズを計算する。

    Args:
        points: ポリラインの頂点リスト。各頂点は整数座標 {"x": int, "y": int} の形式。2点以上が必須。

    Returns:
        (長さ, 始点, 終点, 中点, 外接矩形の幅, 外接矩形の高さ) のタプル。
    """
    # 始点と終点
    start_point = {"x": float(points[0]["x"]), "y": float(points[0]["y"])}
    end_point = {"x": float(points[-1]["x"]), "y": float(points[-1]["y"])}

    # 中点（全頂点の座標平均）
    sum_x = sum(p["x"] for p in points)
    sum_y = sum(p["y"] for p in points)
    midpoint = {"x": sum_x / len(points), "y": sum_y / len(points)}

    # 線の長さを計算
    total_length = 0.0
    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]
        dx = p2["x"] - p1["x"]
        dy = p2["y"] - p1["y"]
        segment_length = math.hypot(dx, dy)
        total_length += segment_length

    # 外接矩形を計算
    x_coords = [p["x"] for p in points]
    y_coords = [p["y"] for p in points]
    min_x = min(x_coords)
    max_x = max(x_coords)
    min_y = min(y_coords)
    max_y = max(y_coords)
    bbox_width = float(max_x - min_x)
    bbox_height = float(max_y - min_y)

    return total_length, start_point, end_point, midpoint, bbox_width, bbox_height


def get_annotation_polyline_info_list(simple_annotation: dict[str, Any], *, target_label_names: Collection[str] | None = None) -> list[AnnotationPolylineInfo]:
    result = []
    target_label_names_set = set(target_label_names) if target_label_names is not None else None
    for detail in simple_annotation["details"]:
        if detail["data"]["_type"] == "Points":
            label = detail["label"]
            # ラベル名によるフィルタリング
            if target_label_names_set is not None and label not in target_label_names_set:
                continue

            points = detail["data"]["points"]
            point_count = len(points)

            # ポリラインのプロパティを計算
            length, start_point, end_point, midpoint, bbox_width, bbox_height = calculate_polyline_properties(points)

            result.append(
                AnnotationPolylineInfo(
                    project_id=simple_annotation["project_id"],
                    task_id=simple_annotation["task_id"],
                    task_phase=simple_annotation["task_phase"],
                    task_phase_stage=simple_annotation["task_phase_stage"],
                    task_status=simple_annotation["task_status"],
                    input_data_id=simple_annotation["input_data_id"],
                    input_data_name=simple_annotation["input_data_name"],
                    label=label,
                    annotation_id=detail["annotation_id"],
                    point_count=point_count,
                    length=length,
                    start_point=start_point,
                    end_point=end_point,
                    midpoint=midpoint,
                    bounding_box_width=bbox_width,
                    bounding_box_height=bbox_height,
                    attributes=detail["attributes"],
                    points=points,
                    updated_datetime=simple_annotation["updated_datetime"],
                )
            )

    return result


def get_annotation_polyline_info_list_from_annotation_path(
    annotation_path: Path,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    target_label_names: Collection[str] | None = None,
) -> list[AnnotationPolylineInfo]:
    annotation_polyline_list = []
    target_task_ids = set(target_task_ids) if target_task_ids is not None else None
    iter_parser = lazy_parse_simple_annotation_by_input_data(annotation_path)
    logger.info(f"アノテーションZIPまたはディレクトリ'{annotation_path}'を読み込みます。")
    for index, parser in enumerate(iter_parser):
        if (index + 1) % 10000 == 0:
            logger.info(f"{index + 1}  件目のJSONを読み込み中")
        if target_task_ids is not None and parser.task_id not in target_task_ids:
            continue
        dict_simple_annotation = parser.load_json()
        if task_query is not None and not match_annotation_with_task_query(dict_simple_annotation, task_query):
            continue
        sub_annotation_polyline_list = get_annotation_polyline_info_list(dict_simple_annotation, target_label_names=target_label_names)
        annotation_polyline_list.extend(sub_annotation_polyline_list)
    return annotation_polyline_list


def create_df(
    annotation_polyline_list: list[AnnotationPolylineInfo],
) -> pandas.DataFrame:
    """
    CSV出力用のDataFrameを作成する。

    Notes:
        points列は含めない。CSVに含めると列の長さが非常に大きくなるため。
        attributes列は、キーごとに別々の列（attributes.<key>の形式）として出力する。
        pandas.json_normalizeを使用してネストした辞書を自動的に展開する。

    """
    # 基本列の定義
    base_columns = [
        "project_id",
        "task_id",
        "task_status",
        "task_phase",
        "task_phase_stage",
        "input_data_id",
        "input_data_name",
        "updated_datetime",
        "label",
        "annotation_id",
        "point_count",
        "length",
        "start_point.x",
        "start_point.y",
        "end_point.x",
        "end_point.y",
        "midpoint.x",
        "midpoint.y",
        "bounding_box_width",
        "bounding_box_height",
    ]

    if len(annotation_polyline_list) == 0:
        # 件数が0件のときも列ヘッダを出力する
        return pandas.DataFrame(columns=base_columns)

    # pandas.json_normalizeを使用してネストした辞書を展開
    # start_point, end_point, midpoint（辞書）とattributes（辞書）が自動的に展開される
    df = pandas.json_normalize([e.model_dump() for e in annotation_polyline_list])

    # attributes列を抽出してソート
    attributes_columns = sorted([col for col in df.columns if col.startswith("attributes.")])
    # 列の順序を設定
    columns = base_columns + attributes_columns

    return df[columns]


def print_annotation_polyline(
    annotation_path: Path,
    output_file: Path,
    output_format: FormatArgument,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    target_label_names: Collection[str] | None = None,
) -> None:
    annotation_polyline_list = get_annotation_polyline_info_list_from_annotation_path(
        annotation_path,
        target_task_ids=target_task_ids,
        task_query=task_query,
        target_label_names=target_label_names,
    )

    logger.info(f"{len(annotation_polyline_list)} 件のポリラインアノテーションの情報を出力します。 :: output='{output_file}'")

    if output_format == FormatArgument.CSV:
        df = create_df(annotation_polyline_list)
        print_csv(df, output_file)

    elif output_format in [FormatArgument.PRETTY_JSON, FormatArgument.JSON]:
        json_is_pretty = output_format == FormatArgument.PRETTY_JSON
        # Pydantic BaseModelを使用したJSON処理
        print_json(
            [e.model_dump() for e in annotation_polyline_list],
            is_pretty=json_is_pretty,
            output=output_file,
        )

    else:
        raise ValueError(f"出力形式 '{output_format}' はサポートされていません。")


class ListAnnotationPolyline(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_zip list_polyline_annotation: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False
        return True

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id: str | None = args.project_id
        if project_id is not None:
            super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
            project, _ = self.service.api.get_project(project_id)
            if project["input_data_type"] != InputDataType.IMAGE.value:
                print(f"project_id='{project_id}'であるプロジェクトは画像プロジェクトでないので、終了します", file=sys.stderr)  # noqa: T201
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None
        label_name_list = get_list_from_args(args.label_name) if args.label_name is not None else None

        output_file: Path = args.output
        output_format = FormatArgument(args.format)

        downloading_obj = DownloadingFile(self.service)

        def download_and_print_annotation_polyline(project_id: str, temp_dir: Path, *, is_latest: bool) -> None:
            local_annotation_path = temp_dir / f"{project_id}__annotation.zip"
            downloading_obj.download_annotation_zip(
                project_id,
                dest_path=local_annotation_path,
                is_latest=is_latest,
            )
            print_annotation_polyline(
                local_annotation_path,
                output_file,
                output_format,
                target_task_ids=task_id_list,
                task_query=task_query,
                target_label_names=label_name_list,
            )

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_print_annotation_polyline(project_id=project_id, temp_dir=args.temp_dir, is_latest=args.latest)
            else:
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_print_annotation_polyline(
                        project_id=project_id,
                        temp_dir=Path(str_temp_dir),
                        is_latest=args.latest,
                    )
        else:
            assert annotation_path is not None
            print_annotation_polyline(
                annotation_path,
                output_file,
                output_format,
                target_task_ids=task_id_list,
                task_query=task_query,
                target_label_names=label_name_list,
            )


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--annotation",
        type=str,
        help="アノテーションzip、またはzipを展開したディレクトリを指定します。",
    )

    group.add_argument("-p", "--project_id", type=str, help="project_id。アノテーションZIPをダウンロードします。")

    argument_parser.add_format(
        choices=[FormatArgument.CSV, FormatArgument.JSON, FormatArgument.PRETTY_JSON],
        default=FormatArgument.CSV,
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
        "--label_name",
        type=str,
        nargs="+",
        help="指定したラベル名のポリラインアノテーションのみを対象にします。複数指定できます。",
    )

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

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListAnnotationPolyline(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_polyline_annotation"
    subcommand_help = "アノテーションZIPからポリラインアノテーションの座標情報と属性情報を出力します。"
    epilog = "アノテーションZIPをダウンロードする場合は、オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
