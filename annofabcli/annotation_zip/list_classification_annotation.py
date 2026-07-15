from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import ProjectMemberRole
from dataclasses_json import DataClassJsonMixin

import annofabcli.common.cli
from annofabcli.common.annofab.annotation_editor_url import (
    ANNOTATION_EDITOR_TYPE_CHOICES,
    AnnotationEditorType,
    create_annotation_editor_url,
    get_annotation_editor_type_from_input_data_type,
)
from annofabcli.common.annofab.annotation_zip import lazy_parse_simple_annotation_by_input_data
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE, ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.download import DownloadingFile
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import (
    AnnofabApiFacade,
    TaskQuery,
    match_annotation_with_task_query,
)
from annofabcli.common.utils import print_csv, print_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClassificationAnnotationInfo(DataClassJsonMixin):
    project_id: str
    task_id: str
    task_phase: str
    task_phase_stage: int
    task_status: str

    input_data_id: str
    input_data_name: str

    updated_datetime: str | None
    """アノテーションJSONに格納されているアノテーションの更新日時。"""

    label: str
    annotation_id: str
    annotation_editor_url: str
    attributes: dict[str, str | int | bool]


def get_classification_annotation_info_list(
    simple_annotation: dict[str, Any],
    *,
    target_label_names: Collection[str] | None = None,
    annotation_editor_type: AnnotationEditorType | None = None,
) -> list[ClassificationAnnotationInfo]:
    """
    1個のアノテーションJSONからClassificationアノテーションの情報を取得します。

    Args:
        simple_annotation: アノテーションJSONファイルの内容
        target_label_names: 絞り込むラベル名
        annotation_editor_type: アノテーションエディタの種類
    """
    result = []
    target_label_names_set = set(target_label_names) if target_label_names is not None else None
    for detail in simple_annotation["details"]:
        if detail["data"]["_type"] != "Classification":
            continue

        label = detail["label"]
        if target_label_names_set is not None and label not in target_label_names_set:
            continue

        result.append(
            ClassificationAnnotationInfo(
                project_id=simple_annotation["project_id"],
                task_id=simple_annotation["task_id"],
                task_phase=simple_annotation["task_phase"],
                task_phase_stage=simple_annotation["task_phase_stage"],
                task_status=simple_annotation["task_status"],
                input_data_id=simple_annotation["input_data_id"],
                input_data_name=simple_annotation["input_data_name"],
                label=label,
                annotation_id=detail["annotation_id"],
                annotation_editor_url=create_annotation_editor_url(simple_annotation, detail, annotation_editor_type),
                updated_datetime=simple_annotation["updated_datetime"],
                attributes=detail["attributes"],
            )
        )

    return result


def get_classification_annotation_info_list_from_annotation_path(
    annotation_path: Path,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    target_label_names: Collection[str] | None = None,
    annotation_editor_type: AnnotationEditorType | None = None,
) -> list[ClassificationAnnotationInfo]:
    classification_annotation_list = []
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
        sub_classification_annotation_list = get_classification_annotation_info_list(
            dict_simple_annotation,
            target_label_names=target_label_names,
            annotation_editor_type=annotation_editor_type,
        )
        classification_annotation_list.extend(sub_classification_annotation_list)
    return classification_annotation_list


def create_df(
    classification_annotation_list: list[ClassificationAnnotationInfo],
) -> pandas.DataFrame:
    base_columns = [
        "project_id",
        "task_id",
        "task_phase",
        "task_phase_stage",
        "task_status",
        "input_data_id",
        "input_data_name",
        "updated_datetime",
        "label",
        "annotation_id",
        "annotation_editor_url",
    ]

    if not classification_annotation_list:
        return pandas.DataFrame(columns=base_columns)

    tmp_classification_annotation_list = [e.to_dict(encode_json=True) for e in classification_annotation_list]
    df = pandas.json_normalize(tmp_classification_annotation_list)

    attribute_columns = sorted(col for col in df.columns if col.startswith("attributes."))
    columns = base_columns + attribute_columns

    return df[columns]


def print_classification_annotation(
    annotation_path: Path,
    output_file: Path,
    output_format: OutputFormat,
    *,
    target_task_ids: Collection[str] | None = None,
    task_query: TaskQuery | None = None,
    target_label_names: Collection[str] | None = None,
    annotation_editor_type: AnnotationEditorType | None = None,
) -> None:
    classification_annotation_list = get_classification_annotation_info_list_from_annotation_path(
        annotation_path,
        target_task_ids=target_task_ids,
        task_query=task_query,
        target_label_names=target_label_names,
        annotation_editor_type=annotation_editor_type,
    )

    logger.info(f"{len(classification_annotation_list)} 件の全体アノテーションの情報を出力します。 :: output='{output_file}'")

    if output_format == OutputFormat.CSV:
        df = create_df(classification_annotation_list)
        print_csv(df, output_file)

    elif output_format in [OutputFormat.PRETTY_JSON, OutputFormat.JSON]:
        json_is_pretty = output_format == OutputFormat.PRETTY_JSON
        print_json(
            [e.to_dict(encode_json=True) for e in classification_annotation_list],
            is_pretty=json_is_pretty,
            output=output_file,
        )

    else:
        raise ValueError(f"出力形式 '{output_format}' はサポートされていません。")


class ListClassificationAnnotation(CommandLine):
    COMMON_MESSAGE = "annofabcli annotation_zip list_classification_annotation: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False
        if args.annotation_editor_type is not None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --annotation_editor_type: '--annotation'を指定したときのみ指定できます。",
                file=sys.stderr,
            )
            return False
        return True

    def main(self) -> None:
        args = self.args

        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        project_id: str | None = args.project_id
        annotation_editor_type: AnnotationEditorType | None = args.annotation_editor_type
        if project_id is not None:
            super().validate_project(project_id, project_member_roles=[ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
            project, _ = self.service.api.get_project(project_id)
            annotation_editor_type = get_annotation_editor_type_from_input_data_type(project["input_data_type"])

        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None
        label_name_list = get_list_from_args(args.label_name) if args.label_name is not None else None

        output_file: Path = args.output
        output_format = OutputFormat(args.format)

        downloading_obj = DownloadingFile(self.service)

        def download_and_print_classification_annotation(project_id: str, temp_dir: Path, *, is_latest: bool) -> None:
            local_annotation_path = downloading_obj.download_annotation_zip_to_dir(
                project_id,
                temp_dir,
                is_latest=is_latest,
            )
            print_classification_annotation(
                local_annotation_path,
                output_file,
                output_format,
                target_task_ids=task_id_list,
                task_query=task_query,
                target_label_names=label_name_list,
                annotation_editor_type=annotation_editor_type,
            )

        if project_id is not None:
            if args.temp_dir is not None:
                download_and_print_classification_annotation(project_id=project_id, temp_dir=args.temp_dir, is_latest=args.latest)
            else:
                with tempfile.TemporaryDirectory() as str_temp_dir:
                    download_and_print_classification_annotation(
                        project_id=project_id,
                        temp_dir=Path(str_temp_dir),
                        is_latest=args.latest,
                    )
        else:
            assert annotation_path is not None
            print_classification_annotation(
                annotation_path,
                output_file,
                output_format,
                target_task_ids=task_id_list,
                task_query=task_query,
                target_label_names=label_name_list,
                annotation_editor_type=annotation_editor_type,
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

    parser.add_argument(
        "--annotation_editor_type",
        type=str,
        choices=ANNOTATION_EDITOR_TYPE_CHOICES,
        help="``--annotation`` で指定したアノテーションZIPに対応するアノテーションエディタの種類を指定します。未指定の場合は ``image`` としてURLを生成します。",
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
        "--label_name",
        type=str,
        nargs="+",
        help="指定したラベル名の全体アノテーションのみを対象にします。複数指定できます。",
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
    ListClassificationAnnotation(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "list_classification_annotation"
    subcommand_help = "アノテーションZIPから全体アノテーション（Classification）の情報を出力します。"
    epilog = "アノテーションZIPをダウンロードする場合は、オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help, epilog=epilog)
    parse_args(parser)
    return parser
