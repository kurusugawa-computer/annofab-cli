from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from collections.abc import Collection
from functools import partial
from pathlib import Path

from annofabapi.models import DefaultAnnotationType, InputDataType, ProjectMemberRole

import annofabcli.common.cli
from annofabcli.annotation_zip.visualize_annotation_duration import (
    BIN_COUNT,
    TimeUnit,
    plot_annotation_duration_histogram_by_attribute,
    plot_annotation_duration_histogram_by_label,
)
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.statistics.list_annotation_duration import AnnotationSpecs, AttributeNameKey, AttributeValueKey, ListAnnotationDurationByInputData

logger = logging.getLogger(__name__)

DEPRECATION_MESSAGE = (
    "[DEPRECATED] statistics visualize_annotation_duration は非推奨です。"
    "annotation_zip visualize_annotation_duration_by_label または "
    "annotation_zip visualize_annotation_duration_by_attribute_value を使用してください。"
    "このコマンドは2027-01-01以降の最初のリリースで廃止予定です。"
)
"""旧コマンドの移行先と廃止予定を案内するメッセージ。"""


class VisualizeAnnotationDuration(CommandLine):
    COMMON_MESSAGE = "annofabcli statistics visualize_annotation_duration: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def visualize_annotation_duration(
        self,
        annotation_path: Path,
        output_dir: Path,
        time_unit: TimeUnit,
        *,
        bin_width: int | None = None,
        project_id: str | None = None,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
        exclude_empty_value: bool = False,
        arrange_bin_edge: bool = False,
    ) -> None:
        duration_by_label_html = output_dir / "annotation_duration_by_label.html"
        duration_by_attribute_html = output_dir / "annotation_duration_by_attribute.html"

        # 集計対象の属性を、選択肢系の属性にする
        annotation_specs: AnnotationSpecs | None = None
        non_selective_attribute_name_keys: list[AttributeNameKey] | None = None
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id, annotation_type=DefaultAnnotationType.RANGE.value)
            non_selective_attribute_name_keys = annotation_specs.non_selective_attribute_name_keys()

        annotation_duration_list = ListAnnotationDurationByInputData(
            non_target_attribute_names=non_selective_attribute_name_keys,
        ).get_annotation_duration_list(
            annotation_path,
            target_task_ids=target_task_ids,
            task_query=task_query,
        )

        label_keys: list[str] | None = None
        attribute_value_keys: list[AttributeValueKey] | None = None
        if annotation_specs is not None:
            label_keys = annotation_specs.label_keys()
            attribute_value_keys = annotation_specs.selective_attribute_value_keys()

        project_title = None
        if project_id is not None:
            project, _ = self.service.api.get_project(project_id)
            project_title = project["title"]

        metadata = {
            "project_id": project_id,
            "project_title": project_title,
            "task_query": {k: v for k, v in task_query.to_dict(encode_json=True).items() if v is not None and v is not False} if task_query is not None else None,
            "target_task_ids": target_task_ids,
        }
        plot_annotation_duration_histogram_by_label(
            annotation_duration_list,
            output_file=duration_by_label_html,
            time_unit=time_unit,
            bin_width=bin_width,
            prior_keys=label_keys,
            exclude_empty_value=exclude_empty_value,
            arrange_bin_edge=arrange_bin_edge,
            metadata=metadata,
        )
        plot_annotation_duration_histogram_by_attribute(
            annotation_duration_list,
            output_file=duration_by_attribute_html,
            time_unit=time_unit,
            bin_width=bin_width,
            prior_keys=attribute_value_keys,
            exclude_empty_value=exclude_empty_value,
            arrange_bin_edge=arrange_bin_edge,
            metadata=metadata,
        )

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id: str | None = args.project_id
        if project_id is not None:
            super().require_project_access(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
            project, _ = self.service.api.get_project(project_id)
            if project["input_data_type"] != InputDataType.MOVIE.value:
                logger.warning(f"project_id='{project_id}'であるプロジェクトは、動画プロジェクトでないので、出力される区間アノテーションの長さはすべて0秒になります。")

        output_dir: Path = args.output_dir
        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        func = partial(
            self.visualize_annotation_duration,
            project_id=project_id,
            output_dir=output_dir,
            time_unit=TimeUnit(args.time_unit),
            bin_width=args.bin_width,
            target_task_ids=task_id_list,
            task_query=task_query,
            exclude_empty_value=args.exclude_empty_value,
            arrange_bin_edge=args.arrange_bin_edge,
        )

        if annotation_path is None:
            assert project_id is not None
            downloading_obj = DownloadingFile(self.service)
            if args.temp_dir is not None:
                annotation_path = downloading_obj.download_annotation_zip_to_dir(
                    project_id,
                    args.temp_dir,
                    is_latest=args.latest,
                )
                func(annotation_path=annotation_path)
            else:
                # `NamedTemporaryFile`を使わない理由: Windowsで`PermissionError`が発生するため
                # https://qiita.com/yuji38kwmt/items/c6f50e1fc03dafdcdda0 参考
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    annotation_path = downloading_obj.download_annotation_zip_to_dir(
                        project_id,
                        Path(str_temp_dir),
                        is_latest=args.latest,
                    )
                    func(annotation_path=annotation_path)

        else:
            func(annotation_path=annotation_path)


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "--annotation",
        type=str,
        required=False,
        help="アノテーションzip、またはzipを展開したディレクトリを指定します。指定しない場合はAnnofabからダウンロードします。",
    )

    parser.add_argument(
        "-p",
        "--project_id",
        type=str,
        required=False,
        help="project_id。``--annotation`` が未指定のときは必須です。``--annotation`` が指定されているときに ``--project_id`` を指定すると、アノテーション仕様を参照して、集計対象の属性やグラフの順番が決まります。",  # noqa: E501
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリのパス")

    parser.add_argument(
        "--exclude_empty_value",
        action="store_true",
        help="指定すると、すべてのタスクで区間アノテーションの長さが0であるヒストグラムを描画しません。",
    )

    parser.add_argument(
        "--arrange_bin_edge",
        action="store_true",
        help="指定すると、ヒストグラムのデータの範囲とビンの幅がすべてのヒストグラムで一致します。",
    )

    parser.add_argument(
        "--bin_width",
        type=int,
        help=f"ヒストグラムのビンの幅を指定します。単位は「秒」です。指定しない場合は、ビンの個数が{BIN_COUNT}になるようにビンの幅が調整されます。",
    )

    parser.add_argument(
        "--time_unit",
        type=str,
        default=TimeUnit.SECOND.value,
        choices=[e.value for e in TimeUnit],
        help="動画の長さの時間単位を指定します。",
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

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    logger.warning(DEPRECATION_MESSAGE)
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeAnnotationDuration(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "visualize_annotation_duration"
    subcommand_help = "[非推奨・2027-01-01以降の最初のリリースで廃止予定] ラベルごとまたは属性値ごとに区間アノテーションの長さをヒストグラムで可視化したファイルを出力します。"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=DEPRECATION_MESSAGE, epilog=epilog)
    parse_args(parser)
    return parser
