import argparse
import logging
import os
import shutil
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from annofabapi.models import TaskStatus
from annofabapi.parser import SimpleAnnotationParser, lazy_parse_simple_annotation_dir, lazy_parse_simple_annotation_zip

import annofabcli
import annofabcli.common.cli
from annofabcli.common.facade import TaskQuery
from annofabcli.common.image import IsParserFunc

logger = logging.getLogger(__name__)


@dataclass
class FilterQuery:
    task_query: Optional[TaskQuery] = None
    task_id_set: Optional[Set[str]] = None
    exclude_task_id_set: Optional[Set[str]] = None
    input_data_id_set: Optional[Set[str]] = None
    exclude_input_data_id_set: Optional[Set[str]] = None
    input_data_name_set: Optional[Set[str]] = None
    exclude_input_data_name_set: Optional[Set[str]] = None


def _match_task_query(annotation: Dict[str, Any], task_query: Optional[TaskQuery]) -> bool:
    if task_query is None:
        return True

    if task_query.status is not None and annotation["task_status"] != task_query.status.value:
        return False

    if task_query.phase is not None and annotation["task_phase"] != task_query.phase:
        return False

    if task_query.phase_stage is not None and annotation["task_phase_stage"] != task_query.phase_stage:
        return False

    return True


def match_query(annotation: Dict[str, Any], filter_query: FilterQuery) -> bool:  # pylint: disable=too-many-return-statements
    if filter_query.task_query is not None and not _match_task_query(annotation, filter_query.task_query):
        return False

    # xxx_set は1個のみ指定されていること前提なので、elif を羅列する
    if filter_query.task_id_set is not None and annotation["task_id"] not in filter_query.task_id_set:
        return False
    elif filter_query.exclude_task_id_set is not None and annotation["task_id"] in filter_query.exclude_task_id_set:
        return False
    elif (
        filter_query.input_data_id_set is not None and annotation["input_data_id"] not in filter_query.input_data_id_set
    ):
        return False
    elif (
        filter_query.exclude_input_data_id_set is not None
        and annotation["input_data_id"] in filter_query.exclude_input_data_id_set
    ):
        return False
    elif (
        filter_query.input_data_name_set is not None
        and annotation["input_data_name"] not in filter_query.input_data_name_set
    ):
        return False
    elif (
        filter_query.exclude_input_data_name_set is not None
        and annotation["input_data_name"] in filter_query.exclude_input_data_name_set
    ):
        return False

    return True


def create_outer_filepath_dict(namelist: List[str]) -> Dict[str, List[str]]:
    """
    外部アノテーションのファイルパス一覧

    Args:
        namelist: zipファイル内のファイル一覧

    Returns:

    """
    d = defaultdict(list)
    for name in namelist:
        tmp = name.split("/")
        if len(tmp) != 3:
            continue
        dirname = f"{tmp[0]}/{tmp[1]}"
        d[dirname].append(name)
    return d


class FilterAnnotation:
    @staticmethod
    def create_is_target_parser_func(
        task_status_complete: bool = False, task_id_list: Optional[List[str]] = None
    ) -> IsParserFunc:
        def is_target_parser(parser: SimpleAnnotationParser) -> bool:
            simple_annotation = parser.parse()
            if task_status_complete:
                if simple_annotation.task_status != TaskStatus.COMPLETE:
                    logger.debug(
                        f"task_statusがcompleteでない( {simple_annotation.task_status.value})ため、"
                        f"{simple_annotation.task_id}, {simple_annotation.input_data_name} はスキップします。"
                    )
                    return False

            if task_id_list is not None and len(task_id_list) > 0:
                if simple_annotation.task_id not in task_id_list:
                    logger.debug(
                        f"画像化対象外のタスク {simple_annotation.task_id} であるため、 {simple_annotation.input_data_name} はスキップします。"
                    )
                    return False

            return True

        return is_target_parser


    @staticmethod
    def filter_annotation_zip(annotation_zip: Path, filter_query: FilterQuery, output_dir: Path):
        with zipfile.ZipFile(str(annotation_zip)) as zip_file:
            zip_filepath_dict = create_outer_filepath_dict(zip_file.namelist())
            count = 0
            for parser in lazy_parse_simple_annotation_zip(annotation_zip):

                if not match_query(parser.load_json(), filter_query):
                    continue

                # JSONを展開
                zip_file.extract(parser.json_file_path, str(output_dir))
                # 塗りつぶしアノテーションが格納されているディレクトリを展開
                outer_annotation_dir = os.path.splitext(parser.json_file_path)[0]
                outer_annotation_file_list = zip_filepath_dict.get(outer_annotation_dir)
                if outer_annotation_file_list is not None:
                    for outer_annotation_file in outer_annotation_file_list:
                        zip_file.extract(outer_annotation_file, str(output_dir))
                count += 1
                if count % 10000 == 0:
                    logger.debug(f"{count} 件のJSONファイルとそれに紐づく塗りつぶし画像を {output_dir} に展開しました。")

    @staticmethod
    def filter_annotation_dir(annotation_dir: Path, filter_query: FilterQuery, output_dir: Path):
        count = 0
        for parser in lazy_parse_simple_annotation_dir(annotation_dir):
            if not match_query(parser.load_json(), filter_query):
                continue

            # JSONファイルをコピー
            dest_task_id_dir = output_dir / parser.task_id
            dest_task_id_dir.mkdir(exist_ok=True, parents=True)
            shutil.copy(str(annotation_dir / parser.json_file_path), str(dest_task_id_dir))
            # 塗りつぶしアノテーションファイルをコピー
            outer_annotation_dir = annotation_dir / os.path.splitext(parser.json_file_path)[0]
            if outer_annotation_dir.exists():
                shutil.copytree(str(outer_annotation_dir), str(output_dir))

            count += 1
            if count % 10000 == 0:
                logger.debug(f"{count} 件のJSONファイルとそれに紐づく塗りつぶし画像を {output_dir} をコピーしました。")

    @staticmethod
    def create_filter_query(args: argparse.Namespace) -> FilterQuery:
        task_query = (
            TaskQuery.from_dict(annofabcli.common.cli.get_json_from_args(args.task_query))
            if args.task_query is not None
            else None
        )

        task_id_set = set(annofabcli.common.cli.get_list_from_args(args.task_id)) if args.task_id is not None else None
        exclude_task_id_set = (
            set(annofabcli.common.cli.get_list_from_args(args.exclude_task_id))
            if args.exclude_task_id is not None
            else None
        )
        input_data_id_set = (
            set(annofabcli.common.cli.get_list_from_args(args.input_data_id))
            if args.input_data_id is not None
            else None
        )
        exclude_input_data_id_set = (
            set(annofabcli.common.cli.get_list_from_args(args.exclude_input_data_id))
            if args.exclude_input_data_id is not None
            else None
        )
        input_data_name_set = (
            set(annofabcli.common.cli.get_list_from_args(args.input_data_name))
            if args.input_data_name is not None
            else None
        )
        exclude_input_data_name_set = (
            set(annofabcli.common.cli.get_list_from_args(args.exclude_input_data_name))
            if args.exclude_input_data_name is not None
            else None
        )

        return FilterQuery(
            task_query=task_query,
            task_id_set=task_id_set,
            exclude_task_id_set=exclude_task_id_set,
            input_data_id_set=input_data_id_set,
            exclude_input_data_id_set=exclude_input_data_id_set,
            input_data_name_set=input_data_name_set,
            exclude_input_data_name_set=exclude_input_data_name_set,
        )

    def main(self, args: argparse.Namespace):
        logger.info(f"args: {args}")

        annotation_path: Path = args.annotation
        output_dir: Path = args.output_dir
        output_dir.mkdir(exist_ok=True, parents=True)
        filter_query = self.create_filter_query(args)

        if zipfile.is_zipfile(annotation_path):
            self.filter_annotation_zip(annotation_path, filter_query=filter_query, output_dir=output_dir)
        elif annotation_path.is_dir():
            self.filter_annotation_dir(annotation_path, filter_query=filter_query, output_dir=output_dir)
        else:
            logger.info("TODO")
            return


def main(args):
    FilterAnnotation().main(args)


def parse_args(parser: argparse.ArgumentParser):

    parser.add_argument("--annotation", type=Path, required=True, help="アノテーションzip、またはzipを展開したディレクトリ")

    parser.add_argument(
        "-tq",
        "--task_query",
        type=str,
        help="タスクを絞り込むためのクエリ条件をJSON形式で指定します。使用できるキーは status, phase, phase_stage です。"
        "`file://`を先頭に付けると、JSON形式のファイルを指定できます。",
    )

    id_name_list_group = parser.add_mutually_exclusive_group()
    id_name_list_group.add_argument(
        "-t",
        "--task_id",
        type=str,
        nargs="+",
        help="抽出するタスクのtask_idを指定してください。" + "`file://`を先頭に付けると、task_id の一覧が記載されたファイルを指定できます。",
    )

    id_name_list_group.add_argument(
        "--exclude_task_id",
        type=str,
        nargs="+",
        help="除外するタスクのtask_idを指定してください。" + "`file://`を先頭に付けると、task_id の一覧が記載されたファイルを指定できます。",
    )

    id_name_list_group.add_argument(
        "-i",
        "--input_data_id",
        type=str,
        nargs="+",
        help="抽出する入力データのinput_data_idを指定してください。" + "`file://`を先頭に付けると、input_data_id の一覧が記載されたファイルを指定できます。",
    )
    id_name_list_group.add_argument(
        "--exclude_input_data_id",
        type=str,
        nargs="+",
        help="除外する入力データのinput_data_idを指定してください。" + "`file://`を先頭に付けると、input_data_id の一覧が記載されたファイルを指定できます。",
    )

    id_name_list_group.add_argument(
        "--input_data_name",
        type=str,
        nargs="+",
        help="抽出する入力データのinput_data_nameを指定してください。" + "`file://`を先頭に付けると、input_data_name の一覧が記載されたファイルを指定できます。",
    )
    id_name_list_group.add_argument(
        "--exclude_input_data_name",
        type=str,
        nargs="+",
        help="除外する入力データのinput_data_nameを指定してください。" + "`file://`を先頭に付けると、input_data_name の一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "filter_annotation"

    subcommand_help = "アノテーションzipから特定のファイルを絞り込んで、zip展開します。"

    description = "アノテーションzipから特定のファイルを絞り込んで、zip展開します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
