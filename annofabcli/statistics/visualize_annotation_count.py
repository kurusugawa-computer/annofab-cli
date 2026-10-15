from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from collections.abc import Collection, Sequence
from functools import partial
from pathlib import Path

from annofabapi.models import ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.annotation_count import AnnotationCounter, AnnotationSpecs, AttributeNameKey, AttributeValueKey, GroupBy, ListAnnotationCounterByInputData, ListAnnotationCounterByTask
from annofabcli.common.annotation_count_histogram import (
    BIN_COUNT,
    plot_attribute_histogram,
    plot_label_histogram,
)
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.download import DownloadingFile
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery

logger = logging.getLogger(__name__)

DEPRECATED_MESSAGE = (
    "[DEPRECATED] :: `statistics visualize_annotation_count` コマンドは非推奨です。"
    "ラベルごとの可視化は `annotation_zip visualize_annotation_count_by_label` コマンドを使用してください。"
    "属性値ごとの可視化は `annotation_zip visualize_annotation_count_by_attribute_value` コマンドを使用してください。 "
    "`statistics visualize_annotation_count` コマンドは2027/01/01以降に廃止予定です。"
)


class VisualizeAnnotationCount(CommandLine):
    COMMON_MESSAGE = "annofabcli statistics visualize_annotation_count: error:"

    def validate(self, args: argparse.Namespace) -> bool:
        if args.project_id is None and args.annotation is None:
            print(  # noqa: T201
                f"{self.COMMON_MESSAGE} argument --project_id: '--annotation'が未指定のときは、'--project_id' を指定してください。",
                file=sys.stderr,
            )
            return False

        return True

    def visualize_annotation_count(
        self,
        group_by: GroupBy,
        annotation_path: Path,
        output_dir: Path,
        *,
        bin_width: int | None = None,
        project_id: str | None = None,
        target_task_ids: Collection[str] | None = None,
        task_query: TaskQuery | None = None,
        exclude_empty_value: bool = False,
        arrange_bin_edge: bool = False,
    ) -> None:
        labels_count_html = output_dir / "labels_count.html"
        attributes_count_html = output_dir / "attributes_count.html"

        # 集計対象の属性を、選択肢系の属性にする
        annotation_specs: AnnotationSpecs | None = None
        non_selective_attribute_name_keys: list[AttributeNameKey] | None = None
        if project_id is not None:
            annotation_specs = AnnotationSpecs(self.service, project_id)
            non_selective_attribute_name_keys = annotation_specs.non_selective_attribute_name_keys()

        counter_list: Sequence[AnnotationCounter] = []
        if group_by == GroupBy.INPUT_DATA_ID:
            counter_list = ListAnnotationCounterByInputData(
                non_target_attribute_names=non_selective_attribute_name_keys,
            ).get_annotation_counter_list(
                annotation_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
            )

        elif group_by == GroupBy.TASK_ID:
            counter_list = ListAnnotationCounterByTask(
                non_target_attribute_names=non_selective_attribute_name_keys,
            ).get_annotation_counter_list(
                annotation_path,
                target_task_ids=target_task_ids,
                task_query=task_query,
            )

        else:
            raise RuntimeError(f"group_by='{group_by}'が対象外です。")

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

        plot_label_histogram(
            counter_list,
            group_by=group_by,
            output_file=labels_count_html,
            bin_width=bin_width,
            prior_keys=label_keys,
            exclude_empty_value=exclude_empty_value,
            arrange_bin_edge=arrange_bin_edge,
            metadata=metadata,
        )
        plot_attribute_histogram(
            counter_list,
            group_by=group_by,
            output_file=attributes_count_html,
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

        output_dir: Path = args.output_dir
        annotation_path = Path(args.annotation) if args.annotation is not None else None

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        task_query = TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query)) if args.task_query is not None else None

        group_by = GroupBy(args.group_by)

        func = partial(
            self.visualize_annotation_count,
            project_id=project_id,
            group_by=group_by,
            output_dir=output_dir,
            target_task_ids=task_id_list,
            task_query=task_query,
            bin_width=args.bin_width,
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
        "--group_by",
        type=str,
        choices=[GroupBy.TASK_ID.value, GroupBy.INPUT_DATA_ID.value],
        default=GroupBy.TASK_ID.value,
        help="アノテーションの個数をどの単位で集約するかを指定します。",
    )

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

    parser.set_defaults(subcommand_func=main)


def main(args: argparse.Namespace) -> None:
    logger.warning(DEPRECATED_MESSAGE)
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    VisualizeAnnotationCount(service, facade, args).main()


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    subcommand_name = "visualize_annotation_count"
    subcommand_help = "[DEPRECATED] 各ラベル、各属性値のアノテーション数をヒストグラムで可視化します。"
    description = f"{subcommand_help}\n{DEPRECATED_MESSAGE}"
    epilog = "オーナロールまたはアノテーションユーザロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description, epilog=epilog)
    parse_args(parser)
    return parser
